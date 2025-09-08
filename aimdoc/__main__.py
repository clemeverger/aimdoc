#!/usr/bin/env python3
"""
Aimdoc CLI - Smart Documentation Scraper for AI Development
"""

import typer
from pathlib import Path
from typing import Optional
from rich.console import Console

from .cli.commands import scrape_command

console = Console()

app = typer.Typer(
    name="aimdoc",
    help="🤖 Smart Documentation Scraper for AI Development",
    add_completion=False,
)

@app.command()
def scrape(
    url: Optional[str] = typer.Argument(None, help="URL of the documentation site to scrape"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Project name (defaults to domain name)"),
    output_dir: str = typer.Option("./docs", "--output-dir", "-o", help="Output directory for the documentation"),
):
    """
    🕷️ Scrape documentation from a website
    
    Interactive mode will prompt for missing arguments.
    """
    scrape_command(url, name, output_dir)

@app.command()
def version():
    """Show version information"""
    console.print("🤖 [bold blue]Aimdoc v2.0.0[/bold blue] - Smart Documentation Scraper for AI Development")
    console.print("💡 Now running locally - no server required!")

def main():
    """Entry point for the CLI"""
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n👋 [yellow]Goodbye![/yellow]")

if __name__ == "__main__":
    main()