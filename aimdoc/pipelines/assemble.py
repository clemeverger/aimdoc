import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
import re
import sys

class AssemblePipeline:
    """
    A simplified pipeline to assemble markdown files into a clean directory structure.
    It creates one folder per project and mirrors the URL path in the filesystem.
    """

    def __init__(self):
        self.pages = []
        self.output_dir = None
        self.files_created_count = 0

    def open_spider(self, spider):
        """Initialize the pipeline and create the main output directory."""
        self.spider = spider
        self.manifest = spider.manifest

        project_name = self.manifest.get('name', 'default-project')
        
        # Use absolute paths to avoid working directory confusion
        # Get the current working directory (should be the job directory)
        job_dir = Path(os.getcwd()).resolve()
        
        # Log the current working directory for debugging
        spider.logger.info(f"Current working directory: {job_dir}")
        
        # Create docs directory inside the job directory, not at the project root
        # This ensures files are created where job_service.py expects them
        docs_dir = job_dir / 'docs'
        docs_dir.mkdir(exist_ok=True)
        self.output_dir = docs_dir / project_name
        self.output_dir.mkdir(parents=True, exist_ok=True)
        spider.logger.info(f"Assembling documentation in: {self.output_dir}")

    def process_item(self, item, spider):
        """Collect pages with markdown content."""
        if item.get('md'):
            self.pages.append(dict(item))
        return item

    def close_spider(self, spider):
        """
        Finalize the assembly process: write markdown files, a README,
        and a sources.json metadata file.
        """
        if not self.pages:
            spider.logger.warning("No pages with markdown content to assemble.")
            return

        self.pages.sort(key=lambda p: (p.get('order', 999), p['url']))

        self._generate_markdown_files()
        self._generate_readme()
        self._generate_sources_json()

        spider.logger.info(f"Assembly complete. Generated {len(self.pages)} files.")


    def _generate_markdown_files(self):
        """
        Create a markdown file for each scraped page, mirroring the URL structure.
        """
        for page in self.pages:
            file_path = self._get_path_from_url(page['url'])
            if not file_path:
                continue

            target_path = self.output_dir / file_path

            target_path.parent.mkdir(parents=True, exist_ok=True)

            title = self._escape_yaml(page.get('title', 'Untitled'))
            content = f'---\ntitle: "{title}"\nurl: {page["url"]}\n---\n\n{page["md"]}'

            try:
                with open(target_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                # Update file creation progress
                self.files_created_count += 1
                self._update_file_progress()
            except OSError as e:
                self.spider.logger.error(f"Failed to write file {target_path}: {e}")


    def _get_path_from_url(self, url: str) -> Path | None:
        """
        Converts a URL containing '/docs/' into a relative filesystem path.
        Example: https://example.com/a/b/docs/foo/bar/ -> foo/bar/index.md
        """
        parsed_url = urlparse(url)
        path_str = parsed_url.path
        
        # Find the '/docs/' segment and take everything after it.
        match = re.search(r'(/docs/)(.*)', path_str, re.IGNORECASE)
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
        
    def _generate_readme(self):
        """Generate a simple README.md file listing all created markdown files."""
        readme_path = self.output_dir / 'README.md'
        content = f"# {self.manifest.get('name', 'Documentation')}\n\n"
        content += "## All Pages\n\n"

        for page in self.pages:
            file_path = self._get_path_from_url(page['url'])
            if file_path:
                title = page.get('title', str(file_path))
                content += f"- [{title}]({file_path})\n"

        try:
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.spider.logger.info(f"Generated README.md at {readme_path}")
        except OSError as e:
            self.spider.logger.error(f"Failed to write README.md: {e}")

    def _generate_sources_json(self):
        """
        Generate a SOURCES.json file with metadata about the scrape.
        """
        sources = [
            {
                'url': page['url'],
                'title': page.get('title', ''),
                'order': page.get('order', 999),
                'fetched_at': page.get('fetched_at', ''),
            }
            for page in self.pages
        ]

        sources_path = self.output_dir / 'sources.json'
        metadata = {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'total_pages': len(sources),
            'manifest_name': self.manifest.get('name', ''),
            'sources': sources,
        }

        try:
            with open(sources_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            self.spider.logger.info(f"Generated sources.json at {sources_path}")
        except OSError as e:
            self.spider.logger.error(f"Failed to write sources.json: {e}")

    def _escape_yaml(self, text: str) -> str:
        """Basic escaping for YAML strings."""
        if not text:
            return ''
        return text.replace('"', '\\"')

    def _update_file_progress(self):
        """Update progress file with files created count"""
        try:
            import json
            manifest_path = getattr(self.spider, 'manifest_path', None)
            if not manifest_path:
                return
                
            manifest_dir = os.path.dirname(manifest_path)
            progress_file = os.path.join(manifest_dir, "progress.json")
            
            # Read existing progress file
            progress_data = {
                "pages_found": 0,
                "pages_scraped": 0,
                "files_created": self.files_created_count,
                "sitemap_processed": True
            }
            
            if os.path.exists(progress_file):
                try:
                    with open(progress_file, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                        progress_data.update(existing_data)
                        progress_data["files_created"] = self.files_created_count
                except Exception:
                    pass
            
            # Write updated progress
            with open(progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, indent=2)
                
        except Exception as e:
            self.spider.logger.warning(f"Failed to update file progress: {e}")