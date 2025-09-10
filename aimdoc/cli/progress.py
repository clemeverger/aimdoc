"""
Rich-based progress tracking for CLI mode
"""

from typing import Optional, Callable
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.panel import Panel
from rich.align import Align
from rich.text import Text

console = Console()

class CLIProgressTracker:
    """
    Progress tracker that integrates with Rich for beautiful CLI progress display
    """
    
    def __init__(self):
        self.progress: Optional[Progress] = None
        self.discovery_task = None
        self.scraping_task = None
        self.conversion_task = None
        
        self.pages_found = 0
        self.pages_scraped = 0
        self.files_created = 0
        
    def start_discovery(self):
        """Start the discovery phase"""
        if self.progress is None:
            self.progress = Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                console=console,
            )
            self.progress.start()
        
        self.discovery_task = self.progress.add_task(
            "🔍 Discovering pages...", 
            total=None
        )
    
    def update_discovery(self, pages_found: int):
        """Update discovery progress"""
        self.pages_found = pages_found
        if self.discovery_task is not None:
            self.progress.update(
                self.discovery_task, 
                description=f"🔍 Found {pages_found} pages to scrape"
            )
    
    def start_scraping(self):
        """Transition to scraping phase"""
        if self.discovery_task is not None:
            self.progress.update(self.discovery_task, completed=True)
            self.progress.remove_task(self.discovery_task)
        
        if self.pages_found > 0:
            self.scraping_task = self.progress.add_task(
                "🕷️  Scraping pages...", 
                total=self.pages_found
            )
        else:
            self.scraping_task = self.progress.add_task(
                "🕷️  Scraping pages...", 
                total=None
            )
    
    def update_scraping(self, pages_scraped: int):
        """Update scraping progress"""
        self.pages_scraped = pages_scraped
        if self.scraping_task is not None:
            if self.pages_found > 0:
                self.progress.update(
                    self.scraping_task,
                    completed=pages_scraped,
                    description=f"🕷️  Scraped {pages_scraped}/{self.pages_found} pages"
                )
            else:
                self.progress.update(
                    self.scraping_task,
                    description=f"🕷️  Scraped {pages_scraped} pages"
                )
    
    def start_conversion(self):
        """Transition to conversion phase"""
        if self.scraping_task is not None:
            self.progress.update(self.scraping_task, completed=True)
            self.progress.remove_task(self.scraping_task)
        
        self.conversion_task = self.progress.add_task(
            "📝 Converting to markdown...", 
            total=None
        )
    
    def update_conversion(self, files_created: int):
        """Update conversion progress"""
        self.files_created = files_created
        if self.conversion_task is not None:
            self.progress.update(
                self.conversion_task,
                description=f"📝 Created {files_created} markdown files"
            )
    
    def complete(self, success: bool = True, summary: Optional[dict] = None):
        """Complete all progress tracking"""
        if self.progress is not None:
            # Clean up any remaining tasks
            for task_id in [self.discovery_task, self.scraping_task, self.conversion_task]:
                if task_id is not None:
                    try:
                        self.progress.remove_task(task_id)
                    except:
                        pass
            
            self.progress.stop()
            self.progress = None
        
        # Show final summary
        if success and summary:
            self._show_success_summary(summary)
        elif success:
            self._show_simple_success()
    
    def _show_success_summary(self, summary: dict):
        """Show detailed success summary"""
        table = Table(show_header=False, show_edge=False, pad_edge=False)
        table.add_column("", style="bold green")
        table.add_column("", style="white")
        
        table.add_row("✅ Files created:", str(summary.get('files_created', self.files_created)))
        table.add_row("📄 Pages scraped:", str(summary.get('pages_scraped', self.pages_scraped)))
        
        if summary.get('pages_discovered'):
            table.add_row("🔍 Pages discovered:", str(summary['pages_discovered']))
        
        if summary.get('pages_failed', 0) > 0:
            table.add_row("⚠️  Pages failed:", str(summary['pages_failed']))
        
        panel = Panel(
            Align.center(table),
            title="[bold green]✨ Scraping Completed Successfully!",
            border_style="green"
        )
        console.print(panel)
    
    def _show_simple_success(self):
        """Show simple success message"""
        console.print("✅ [bold green]Scraping completed successfully![/bold green]")
    
    def show_error(self, error: str):
        """Show error message"""
        if self.progress is not None:
            self.progress.stop()
            self.progress = None
        
        console.print(f"❌ [bold red]Error:[/bold red] {error}")
    
    def show_discovery_status(self, base_url: str, discovery_errors: list = None, internal_crawling_attempted: bool = False):
        """Show discovery status and suggestions"""
        if self.progress is not None:
            self.progress.stop()
            self.progress = None
        
        # Create status message
        status_text = Text()
        
        if internal_crawling_attempted:
            # Both sitemap and internal crawling failed
            status_text.append("❌ Aucune page de documentation trouvée\n\n", style="bold red")
            status_text.append("Aimdoc a tenté :\n", style="yellow")
            status_text.append("  • Découverte par sitemap XML ❌\n", style="yellow")
            status_text.append("  • Découverte par crawling interne ❌\n\n", style="yellow")
        else:
            # Only sitemap failed, internal crawling should start
            status_text.append("⚠️ Aucun sitemap découvert sur ce site\n\n", style="bold yellow")
            status_text.append("🔄 Basculement vers le crawling interne...\n\n", style="blue")
        
        # Add discovery errors if available
        if discovery_errors:
            status_text.append("🔍 Erreurs de découverte détectées :\n", style="bold yellow")
            for i, error in enumerate(discovery_errors, 1):
                if i <= 3:  # Show max 3 errors
                    status_text.append(f"  {i}. {error['url']} - {error['error_type']}\n", style="dim yellow")
            if len(discovery_errors) > 3:
                status_text.append(f"  ... et {len(discovery_errors) - 3} autres erreurs\n", style="dim yellow")
            status_text.append("\n")
        
        # Add appropriate suggestions
        if internal_crawling_attempted:
            status_text.append("💡 Suggestions :\n", style="bold blue")
            status_text.append("  • Vérifiez que l'URL est correcte et accessible\n", style="blue")
            status_text.append("  • Assurez-vous que le site a des pages de documentation\n", style="blue")
            status_text.append("  • Vérifiez que les URLs de documentation contiennent '/docs/'\n", style="blue")
            status_text.append("  • Le site pourrait ne pas avoir de documentation accessible\n", style="blue")
            title_text = "[bold red]🚨 Échec complet de la découverte"
            border_style = "red"
        else:
            status_text.append("ℹ️  Le crawling interne va explorer les liens du site\n", style="blue")
            status_text.append("   pour trouver les pages de documentation...\n", style="blue")
            title_text = "[bold yellow]🔄 Changement de stratégie de découverte"
            border_style = "yellow"
        
        panel = Panel(
            status_text,
            title=title_text,
            border_style=border_style,
            padding=(1, 2)
        )
        console.print(panel)

    def show_internal_crawling_status(self, pages_found: int):
        """Show internal crawling progress"""
        if self.discovery_task is not None:
            self.progress.update(
                self.discovery_task, 
                description=f"🕷️ Crawling interne... {pages_found} pages trouvées"
            )

# Global progress tracker instance for CLI mode
cli_progress = CLIProgressTracker()

def set_cli_progress_callback(spider):
    """Set up CLI progress tracking for a spider"""
    spider._cli_progress_callback = cli_progress
    return cli_progress