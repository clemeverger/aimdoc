import os
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlparse
from pathlib import Path


class AssemblePipeline:
    """Pipeline to assemble markdown files into final output"""
    
    def __init__(self):
        self.pages = []
        self.build_dir = Path('build')
        self.domain_dirs = {}  # Store domain directories
        
    def open_spider(self, spider):
        """Initialize the pipeline"""
        # Ensure build directories exist
        self.build_dir.mkdir(exist_ok=True)
        
        # Store spider reference for accessing manifest
        self.spider = spider
        self.manifest = spider.manifest

    def process_item(self, item, spider):
        """Collect items for final assembly"""
        if item.get('md'):  # Only process items with markdown content
            self.pages.append(dict(item))
        return item

    def close_spider(self, spider):
        """Assemble all pages into final output"""
        if not self.pages:
            spider.logger.warning("No pages to assemble")
            return
        
        # Sort pages by order (from sidebar discovery)
        self.pages.sort(key=lambda p: (p.get('order', 999), p['url']))
        
        # Generate directory structure (domain/path/file.md)
        self._generate_directory_structure()
        
        # Generate metadata files
        self._generate_sources_json()


    def _generate_directory_structure(self):
        """Generate directory structure based on URL paths"""
        
        # First, collect all domains to create metadata files
        domains = set()
        
        for page in self.pages:
            # Extract path structure from URL
            file_path = self._extract_file_path_from_url(page['url'])
            
            if file_path:
                # Extract domain for metadata
                domain = file_path.split('/')[0]
                domains.add(domain)
                
                # Create full path in build directory
                full_path = self.build_dir / file_path
                
                # Create directories if they don't exist
                full_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Generate file content with front matter
                content = self._generate_directory_file_content(page)
                
                # Write file
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                self.spider.logger.info(f"Generated: {file_path}")
        
        # Generate metadata files for each domain
        for domain in domains:
            self._generate_domain_metadata(domain)
    
    def _extract_file_path_from_url(self, url):
        """Extract file path from URL structure with domain prefix"""
        parsed = urlparse(url)
        
        # Extract domain principal from hostname
        domain_folder = self._extract_domain_principal(parsed.netloc)
        
        path_parts = [part for part in parsed.path.split('/') if part]
        
        # Skip if no docs section found
        if 'docs' not in path_parts:
            return None
        
        try:
            docs_index = path_parts.index('docs')
            # Get parts after /docs/
            doc_parts = path_parts[docs_index + 1:]
            
            if not doc_parts:
                return None
            
            # If last part is empty or same as parent, treat as index
            if len(doc_parts) == 1:
                # Single segment like /docs/introduction/ -> domain/introduction.md
                return f"{domain_folder}/{doc_parts[0]}.md"
            else:
                # Multiple segments like /docs/ai-sdk-ui/chatbot -> domain/ai-sdk-ui/chatbot.md
                directory = '/'.join(doc_parts[:-1])
                filename = f"{doc_parts[-1]}.md"
                return f"{domain_folder}/{directory}/{filename}"
                
        except (ValueError, IndexError):
            return None
    
    def _extract_domain_principal(self, netloc):
        """Extract main domain name from netloc"""
        # Remove port if present
        hostname = netloc.split(':')[0]
        
        # Split by dots
        parts = hostname.split('.')
        
        if len(parts) < 2:
            return hostname.lower()
        
        # Remove common prefixes
        prefixes_to_remove = ['www', 'docs', 'api', 'blog', 'help', 'support']
        if parts[0].lower() in prefixes_to_remove and len(parts) > 2:
            parts = parts[1:]
        
        # Get domain without extension
        # For cases like ai-sdk.dev -> ai-sdk
        # For cases like docs.python.org -> python  
        domain_name = parts[0]
        
        # Clean domain name for filesystem
        domain_name = re.sub(r'[^a-zA-Z0-9\-_]', '-', domain_name)
        
        return domain_name.lower()
    
    def _generate_directory_file_content(self, page):
        """Generate content for directory-structured file"""
        
        # Extract chapter info from URL if available from spider metadata
        chapter_info = getattr(page, 'meta', {})
        
        # File front matter
        front_matter = f'''---
title: "{self._escape_yaml(page.get('title', 'Untitled'))}"
url: {page['url']}
fetched_at: {page.get('fetched_at', '')}
---

'''
        
        return front_matter + page['md']


    def _generate_domain_metadata(self, domain):
        """Generate metadata files for a specific domain"""
        
        # Filter pages for this domain
        domain_pages = []
        for page in self.pages:
            file_path = self._extract_file_path_from_url(page['url'])
            if file_path and file_path.startswith(domain + '/'):
                domain_pages.append(page)
        
        if not domain_pages:
            return
            
        domain_dir = self.build_dir / domain
        domain_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate sources.json
        sources = []
        for i, page in enumerate(domain_pages, 1):
            source_info = {
                'url': page['url'],
                'title': page.get('title', ''),
                'order': page.get('order', 999),
                'fetched_at': page.get('fetched_at', ''),
                'etag': page.get('etag', ''),
                'last_modified': page.get('last_modified', ''),
                'hash': page.get('hash', ''),
                'status': page.get('status', 200)
            }
            sources.append(source_info)
        
        sources_path = domain_dir / 'sources.json'
        with open(sources_path, 'w', encoding='utf-8') as f:
            json.dump({
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'total_pages': len(sources),
                'domain': domain,
                'manifest': self.manifest['name'],
                'sources': sources
            }, f, indent=2, ensure_ascii=False)
        
        # Generate pages.json (simplified format for compatibility)
        pages_data = []
        for page in domain_pages:
            pages_data.append({
                'url': page['url'],
                'title': page.get('title', ''),
                'status': page.get('status', 200),
                'fetched_at': page.get('fetched_at', ''),
                'md': page.get('md', '')[:100] + '...' if len(page.get('md', '')) > 100 else page.get('md', '')  # Truncated preview
            })
        
        pages_path = domain_dir / 'pages.json'
        with open(pages_path, 'w', encoding='utf-8') as f:
            json.dump(pages_data, f, indent=2, ensure_ascii=False)
        
        self.spider.logger.info(f"Generated domain metadata: {domain}/sources.json, {domain}/pages.json")

    def _generate_version(self):
        """Generate version string based on current date"""
        now = datetime.now()
        base_version = now.strftime('%Y.%m.%d')
        
        # Check if we need a sequence number (multiple builds same day)
        existing_sources = self.build_dir / 'SOURCES.json'
        if existing_sources.exists():
            try:
                with open(existing_sources, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                existing_version = data.get('version', '')
                if existing_version.startswith(base_version):
                    # Extract sequence number
                    if '-' in existing_version:
                        sequence = int(existing_version.split('-')[-1]) + 1
                        return f'{base_version}-{sequence}'
                    else:
                        return f'{base_version}-2'
            except (json.JSONDecodeError, ValueError):
                pass
        
        return base_version

    def _escape_yaml(self, text):
        """Escape text for YAML values"""
        if not text:
            return ''
        
        # Escape quotes
        text = text.replace('"', '\\"')
        return text
    
    def _generate_sources_json(self):
        """Generate SOURCES.json metadata file"""
        sources = []
        for i, page in enumerate(self.pages, 1):
            source_info = {
                'url': page['url'],
                'title': page.get('title', ''),
                'order': page.get('order', 999),
                'fetched_at': page.get('fetched_at', ''),
                'etag': page.get('etag', ''),
                'last_modified': page.get('last_modified', ''),
                'hash': page.get('hash', ''),
                'status': page.get('status', 200)
            }
            sources.append(source_info)
        
        sources_path = self.build_dir / 'SOURCES.json'
        with open(sources_path, 'w', encoding='utf-8') as f:
            json.dump({
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'total_pages': len(sources),
                'manifest': self.manifest['name'],
                'version': self._generate_version(),
                'sources': sources
            }, f, indent=2, ensure_ascii=False)
        
        self.spider.logger.info(f"Generated SOURCES.json with {len(sources)} pages")