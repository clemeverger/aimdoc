import os
from pathlib import Path
from urllib.parse import urlparse
import re

class AssemblePipeline:
    """
    Optimized pipeline to assemble markdown files with streaming processing.
    Processes pages immediately instead of accumulating in memory.
    """

    def __init__(self):
        self.output_dir = None
        self.files_created_count = 0
        
        # Pre-compile regex patterns for performance
        self._docs_pattern = re.compile(r'(/docs/)(.*)', re.IGNORECASE)

    def open_spider(self, spider):
        """Initialize the pipeline and create the main output directory."""
        self.spider = spider
        self.manifest = spider.manifest

        project_name = self.manifest.get('name', 'default-project')
        
        # For CLI mode, use output directory passed from CLI
        if hasattr(spider, '_cli_output_dir'):
            output_base = Path(spider._cli_output_dir).resolve()
            spider.logger.info(f"CLI mode: Using output directory: {output_base}")
            self.output_dir = output_base / project_name
        else:
            # Fallback for API mode - use job directory with better error handling
            if hasattr(spider, 'job_dir') and spider.job_dir:
                job_dir = Path(spider.job_dir).resolve()
                spider.logger.info(f"API mode: Using job directory: {job_dir}")
            else:
                # Use a safe default instead of getcwd() for better global install compatibility
                import tempfile
                job_dir = Path(tempfile.gettempdir()) / 'aimdoc_jobs'
                spider.logger.warning(f"No job_dir specified, using temporary directory: {job_dir}")
            
            docs_dir = job_dir / 'docs'
            docs_dir.mkdir(parents=True, exist_ok=True)
            self.output_dir = docs_dir / project_name
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        spider.logger.info(f"Final output directory: {self.output_dir.resolve()}")

    def process_item(self, item, spider):
        """Process pages immediately without storing metadata."""
        if 'md' in item:  # Process if md field exists, even if empty
            # Process the page immediately to save memory
            self._process_page_immediately(item)
        return item
    
    def _process_page_immediately(self, page):
        """Process and write a single page to disk immediately."""
        file_path = self._get_path_from_url(page['url'])
        if not file_path:
            return

        target_path = self.output_dir / file_path
        target_path.parent.mkdir(parents=True, exist_ok=True)

        title = self._escape_yaml(page.get('title', 'Untitled'))
        content = f'---\ntitle: "{title}"\nurl: {page["url"]}\n---\n\n{page["md"]}'

        try:
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(content)
            # Update file creation count using Scrapy stats instead of I/O
            self.files_created_count += 1
            if hasattr(self.spider.crawler.stats, 'inc_value'):
                self.spider.crawler.stats.inc_value('files_created')
        except OSError as e:
            self.spider.logger.error(f"Failed to write file {target_path}: {e}")

    def close_spider(self, spider):
        """
        Finalize the assembly process.
        Individual markdown files are already created during processing.
        """
        spider.logger.info(f"Assembly completed: Generated {self.files_created_count} files")
        
        # Store the final count in the crawler for CLI access
        spider.crawler._assemble_pipeline_files_created = self.files_created_count




    def _get_path_from_url(self, url: str) -> Path | None:
        """
        Converts a URL containing '/docs/' into a relative filesystem path.
        Example: https://example.com/a/b/docs/foo/bar/ -> foo/bar/index.md
        """
        parsed_url = urlparse(url)
        path_str = parsed_url.path
        
        # Find the '/docs/' segment and take everything after it (use pre-compiled regex).
        match = self._docs_pattern.search(path_str)
        if not match:
            self.spider.logger.warning(f"URL '{url}' does not contain '/docs/' segment. Skipping.")
            return None
        
        # The relative path is the part after '/docs/'.
        relative_path = match.group(2)

        if not relative_path:
            return Path('index.md')

        if relative_path.endswith('/'):
            return Path(relative_path + 'index.md')
        
        path = Path(relative_path)
        if not path.suffix:
            return path.with_suffix('.md')

        return path

    def _escape_yaml(self, text: str) -> str:
        """Basic escaping for YAML strings."""
        if not text:
            return ''
        return text.replace('"', '\\"')

