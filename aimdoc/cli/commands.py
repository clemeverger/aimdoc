"""
CLI commands for Aimdoc
"""

import tempfile
import json
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.align import Align

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from .utils import extract_domain_name, is_valid_url, ensure_output_dir
from .progress import set_cli_progress_callback
from ..spiders.aimdoc import AimdocSpider

console = Console()

def scrape_command(url: Optional[str] = None, name: Optional[str] = None, output_dir: str = "./docs"):
    """
    Main scrape command - handles the complete scraping workflow
    """
    try:
        # Get URL interactively if not provided
        if not url:
            url = Prompt.ask("📍 Documentation URL")
        
        if not is_valid_url(url):
            console.print("❌ [red]Invalid URL provided[/red]")
            return
        
        # Get project name
        if not name:
            default_name = extract_domain_name(url)
            name = Prompt.ask("📝 Project name", default=default_name)
        
        # Get output directory
        if output_dir == "./docs":
            output_dir = Prompt.ask("📁 Output directory", default="./docs")
        
        # Ensure output directory exists and resolve to absolute path
        output_path = ensure_output_dir(output_dir)
        final_path = output_path / name
        
        # Log resolved paths for debugging
        console.print(f"[dim]Debug: Resolved output path: {output_path.resolve()}[/dim]")
        
        # Show summary
        summary_table = f"""[bold]URL:[/bold] {url}
[bold]Project:[/bold] {name}
[bold]Output:[/bold] {final_path.resolve()}"""
        
        panel = Panel(
            summary_table,
            title="[bold blue]📋 Scraping Configuration",
            border_style="blue",
            padding=(1, 2)
        )
        console.print(panel)
        
        # Skip confirmation if all parameters were provided
        provided_all_params = url and name and output_dir != "./docs"
        if not provided_all_params:
            if not Confirm.ask("🚀 Start scraping?", default=True):
                console.print("Operation cancelled.")
                return
        else:
            console.print("🚀 [bold green]Starting scrape...[/bold green]")
        
        # Start the scraping process with absolute path
        _run_scrapy_spider(url, name, str(output_path.resolve()))
        
        # Show final success message
        console.print(f"\n🎉 [bold green]Success![/bold green] Documentation saved to [bold]{final_path.resolve()}[/bold]")
        
        # Generate README suggestion
        readme_path = final_path / "README.md"
        if readme_path.exists():
            console.print(f"📖 Index file created: [cyan]{readme_path}[/cyan]")
        
    except KeyboardInterrupt:
        console.print("\n⚠️  [yellow]Operation cancelled by user[/yellow]")
    except Exception as e:
        console.print(f"\n❌ [red]Error:[/red] {str(e)}")
        raise

def _run_scrapy_spider(url: str, name: str, output_dir: str):
    """
    Run the Scrapy spider with CLI integration
    """
    # Create temporary manifest for compatibility with existing spider
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        manifest = {
            "url": url,
            "name": name
        }
        json.dump(manifest, f)
        manifest_path = f.name
    
    try:
        # Force aimdoc settings instead of relying on project discovery
        from aimdoc import settings as aimdoc_settings
        
        # Create settings dict from aimdoc.settings module
        settings_dict = {}
        for setting_name in dir(aimdoc_settings):
            if setting_name.isupper():
                settings_dict[setting_name] = getattr(aimdoc_settings, setting_name)
        
        # Create and configure the crawler process with aimdoc settings
        process = CrawlerProcess(settings_dict)
        
        # Set up CLI progress callback (we'll get spider instance later)
        progress_callback = None
        
        # Progress callback will be set up after spider creation
        
        # Add custom signal handlers for phase transitions
        def handle_spider_opened(spider):
            """Handle spider opened signal"""
            progress_callback.start_discovery()
        
        def handle_spider_closed(spider, reason):
            """Handle spider closed signal"""
            if reason == 'finished':
                # Extract final stats for summary
                stats = spider.crawler.stats.get_stats()
                
                # Check for discovery status (sitemap or internal crawling)
                sitemap_failed = stats.get('sitemap_discovery_failed', False)
                internal_crawling_attempted = stats.get('internal_crawling_attempted', False)
                discovery_errors = stats.get('discovery_errors', [])
                
                # Only show error if both sitemap AND internal crawling failed
                if sitemap_failed and not internal_crawling_attempted:
                    # Show discovery status with option for internal crawling
                    base_url = getattr(spider, 'base_url', url)
                    progress_callback.show_discovery_status(base_url, discovery_errors, internal_crawling_attempted)
                    return
                
                # Get files created directly from AssemblePipeline if available
                files_created = stats.get('files_created', 0)
                if hasattr(spider.crawler, '_assemble_pipeline_files_created'):
                    files_created = spider.crawler._assemble_pipeline_files_created
                
                summary = {
                    'files_created': files_created,
                    'pages_scraped': stats.get('progress_pages_scraped', 0),
                    'pages_discovered': stats.get('progress_pages_found', 0),
                    'pages_failed': stats.get('downloader/exception_count', 0)
                }
                progress_callback.complete(success=True, summary=summary)
            else:
                progress_callback.show_error(f"Spider closed with reason: {reason}")
        
        # Connect signals
        from scrapy import signals
        
        # Create a custom spider class with CLI output directory
        class CLIAimdocSpider(AimdocSpider):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._cli_output_dir = output_dir
        
        process.crawl(CLIAimdocSpider, manifest=manifest_path)
        
        # Connect signals to the crawler
        crawler = list(process.crawlers)[0]  # Get the crawler we just added
        spider = crawler.spider  # Get the actual spider instance
        
        # Set up CLI progress callback now that we have the spider
        progress_callback = set_cli_progress_callback(spider)
        
        crawler.signals.connect(handle_spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(handle_spider_closed, signal=signals.spider_closed)
        
        # Also handle stats updates for phase transitions
        def handle_stats_update(stats, spider):
            """Handle stats updates for phase detection"""
            pages_found = stats.get('progress_pages_found', 0)
            pages_scraped = stats.get('progress_pages_scraped', 0)
            files_created = stats.get('files_created', 0)
            
            if pages_found > 0 and pages_scraped == 0:
                # Discovery phase completed, start scraping
                if not hasattr(spider, '_scraping_started'):
                    progress_callback.start_scraping()
                    spider._scraping_started = True
            elif files_created > 0 and pages_scraped > 0:
                # Start conversion phase
                if not hasattr(spider, '_conversion_started'):
                    progress_callback.start_conversion()
                    spider._conversion_started = True
        
        # Note: Scrapy doesn't have a direct stats_changed signal, so we rely on pipeline callbacks
        
        # Start the crawling process
        process.start()
        
    finally:
        # Clean up temporary manifest file
        try:
            Path(manifest_path).unlink()
        except:
            pass

def _generate_readme(output_path: Path, project_name: str):
    """Generate a README.md file with documentation index"""
    readme_path = output_path / "README.md"
    
    # Find all markdown files
    md_files = []
    for md_file in output_path.rglob("*.md"):
        if md_file.name != "README.md":
            relative_path = md_file.relative_to(output_path)
            md_files.append(relative_path)
    
    # Sort files
    md_files.sort()
    
    # Generate README content
    readme_content = f"""# {project_name} Documentation

Generated on {Path().cwd().name} by [Aimdoc](https://github.com/clemeverger/aimdoc)

## 📁 Structure

"""
    
    # Group by directory
    dirs = {}
    for file_path in md_files:
        dir_name = str(file_path.parent) if file_path.parent != Path(".") else "root"
        if dir_name not in dirs:
            dirs[dir_name] = []
        dirs[dir_name].append(file_path)
    
    # Add directory sections
    for dir_name, files in sorted(dirs.items()):
        if dir_name == "root":
            readme_content += "### Root Files\n\n"
        else:
            readme_content += f"### {dir_name}\n\n"
        
        for file_path in sorted(files):
            file_title = file_path.stem.replace('_', ' ').replace('-', ' ').title()
            readme_content += f"- [{file_title}](./{file_path})\n"
        
        readme_content += "\n"
    
    readme_content += """---

*Documentation scraped and organized by [Aimdoc](https://github.com/clemeverger/aimdoc)*
"""
    
    # Write README
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)