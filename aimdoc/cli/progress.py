"""
Rich-based progress tracking for CLI mode
"""

from typing import Optional, Callable
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.panel import Panel
from rich.align import Align

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

# Global progress tracker instance for CLI mode
cli_progress = CLIProgressTracker()

def set_cli_progress_callback(spider):
    """Set up CLI progress tracking for a spider"""
    spider._cli_progress_callback = cli_progress
    return cli_progress