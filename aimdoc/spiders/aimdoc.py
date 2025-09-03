import json
import hashlib
import re
from datetime import datetime, timezone
import fnmatch
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import scrapy
from scrapy import Request

from ..items import DocPage


class AimdocSpider(scrapy.Spider):
    name = "aimdoc"
    
    custom_settings = {
        "HTTPCACHE_ENABLED": True,
        "ROBOTSTXT_OBEY": True,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def __init__(self, manifest, since=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Store manifest path for progress file
        self.manifest_path = manifest
        
        # Load manifest file
        with open(manifest, 'r', encoding='utf-8') as f:
            self.manifest = json.load(f)
        
        self.since = since
        self.discovered_urls = set()
        self.chapter_order = {}
        self.chapters = {}  # Store chapter information extracted from URLs
        self.pages_scraped_count = 0  # Track scraped pages for progress
        
        # Extract minimal configuration from manifest
        self.name_project = self.manifest.get("name", "aimdoc")
        
        # Get base URL and auto-generate discovery URLs
        base_url = self.manifest.get("url", "")
        if not base_url:
            raise ValueError("Manifest must contain 'url' field")
            
        self.base_url = base_url.rstrip('/')
        self.seed_urls = self._generate_discovery_urls()
        
        # Auto-generate scope from base URL
        self.scope_patterns = [f"{self.base_url}/**"]
        
        # Use hardcoded universal selectors
        self.selectors = {
            "title": "h1, .title, .page-title",
            "content": "main, article, .content, .prose, .markdown-body, .doc-content"
        }
        
        # No custom rate limiting - use Scrapy defaults

    def _generate_discovery_urls(self):
        """Generate discovery URLs from base URL"""
        return [
            f"{self.base_url}/robots.txt",
            f"{self.base_url}/sitemap.xml",
            f"{self.base_url}/docs/sitemap.xml",
            f"{self.base_url}/sitemap_index.xml"
        ]
    
    def start_requests(self):
        """Generate initial requests for automatic discovery"""
        self.logger.info(f"=== SPIDER START_REQUESTS ===")
        self.logger.info(f"Base URL: {self.base_url}")
        self.logger.info(f"Project: {self.name_project}")
        self.logger.info(f"Discovery URLs: {self.seed_urls}")
        
        for url in self.seed_urls:
            self.logger.info(f"Creating request for: {url}")
            if url.endswith('robots.txt'):
                self.logger.info(f"-> robots.txt request: {url}")
                yield Request(
                    url,
                    callback=self._parse_robots,
                    meta={"depth": 0},
                    errback=self._handle_discovery_error
                )
            elif url.endswith(('.xml', 'sitemap')):
                self.logger.info(f"-> sitemap request: {url}")
                yield Request(
                    url,
                    callback=self._parse_sitemap,
                    meta={"depth": 0},
                    errback=self._handle_discovery_error
                )


    def _parse_robots(self, response):
        """Parse robots.txt to find sitemap URLs"""
        self.logger.info(f"=== PARSING ROBOTS.TXT: {response.url} ===")
        self.logger.info(f"Response status: {response.status}")
        
        sitemap_urls = []
        
        for line in response.text.split('\n'):
            line = line.strip()
            if line.lower().startswith('sitemap:'):
                sitemap_url = line[8:].strip()
                sitemap_urls.append(sitemap_url)
                self.logger.info(f"Found sitemap in robots.txt: {sitemap_url}")
                
        if sitemap_urls:
            self.logger.info(f"Found {len(sitemap_urls)} sitemap(s) in robots.txt")
            for sitemap_url in sitemap_urls:
                self.logger.info(f"Requesting sitemap: {sitemap_url}")
                yield Request(
                    sitemap_url,
                    callback=self._parse_sitemap,
                    meta={"depth": 0}
                )
        else:
            self.logger.info("No sitemaps found in robots.txt, trying fallback")
            fallback_url = f"{self.base_url}/sitemap.xml"
            self.logger.info(f"Fallback sitemap request: {fallback_url}")
            yield Request(
                fallback_url,
                callback=self._parse_sitemap,
                meta={"depth": 0},
                errback=self._handle_discovery_error
            )
    
    def _handle_discovery_error(self, failure):
        """Handle discovery errors gracefully"""
        self.logger.warning(f"=== DISCOVERY ERROR ===")
        self.logger.warning(f"Failed URL: {failure.request.url}")
        self.logger.warning(f"Error: {failure.value}")
        self.logger.warning(f"Error type: {type(failure.value)}")
        return []

    def parse_page(self, response):
        """Main parsing method for documentation pages"""
        self.logger.info(f"=== PARSING PAGE: {response.url} ===")
        self.logger.info(f"Status: {response.status}, Size: {len(response.body)} bytes")
        
        # Extract page content
        item = self._extract_page_content(response)
        self.logger.info(f"Extracted item: title='{item['title']}', content_length={len(item['html'])}")
        yield item
        
        # Update progress after yielding item
        self._update_scraped_progress()

    def _extract_page_content(self, response):
        """Extract content from a single page"""
        # Extract title
        title_selector = self.selectors.get("title", "h1")
        title_elements = response.css(title_selector)
        title = ""
        if title_elements:
            title = title_elements.xpath("normalize-space(string(.))").get() or ""
        
        # Extract main content
        content_selector = self.selectors.get("content", "main")
        content_elements = response.css(content_selector)
        content_html = ""
        if content_elements:
            content_html = content_elements.get() or ""
        
        # Create item
        item = DocPage(
            url=response.url,
            status=response.status,
            fetched_at=self._now(),
            etag=response.headers.get(b"ETag", b"").decode().strip('"'),
            last_modified=response.headers.get(b"Last-Modified", b"").decode(),
            title=title.strip(),
            html=content_html,
            order=self.chapter_order.get(response.url, 999),
            hash=self._hash_content(content_html)
        )
        
        return item


    def _parse_sitemap(self, response):
        """Parse XML sitemap and extract chapter structure from URLs"""
        self.logger.info(f"=== PARSING SITEMAP: {response.url} ===")
        self.logger.info(f"Response status: {response.status}")
        self.logger.info(f"Response size: {len(response.body)} bytes")
        
        try:
            root = ElementTree.fromstring(response.body)
            # Handle XML namespace
            namespace = {"": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            
            all_url_elements = root.findall(".//url", namespace)
            self.logger.info(f"Found {len(all_url_elements)} total URL elements in sitemap")
            
            urls_found = 0
            urls_skipped_scope = 0
            urls_skipped_not_doc = 0
            urls_skipped_duplicate = 0
            chapter_urls = {}  # Group URLs by chapter
            
            for i, url_element in enumerate(all_url_elements):
                loc_element = url_element.find("loc", namespace)
                if loc_element is not None:
                    url = loc_element.text
                    
                    if i < 5:  # Log first 5 URLs for debugging
                        self.logger.info(f"Processing URL #{i+1}: {url}")
                    
                    # Check if URL is in scope
                    in_scope = self._in_scope(url)
                    if not in_scope:
                        urls_skipped_scope += 1
                        if i < 5:
                            self.logger.info(f"  -> SKIPPED: Not in scope")
                        continue
                    
                    # Check if looks like documentation
                    is_doc = self._is_documentation_url(url)
                    if not is_doc:
                        urls_skipped_not_doc += 1
                        if i < 5:
                            self.logger.info(f"  -> SKIPPED: Not documentation URL")
                        continue
                    
                    # Check if already discovered
                    if url in self.discovered_urls:
                        urls_skipped_duplicate += 1
                        if i < 5:
                            self.logger.info(f"  -> SKIPPED: Duplicate URL")
                        continue
                    
                    if i < 5:
                        self.logger.info(f"  -> ACCEPTED: Will scrape this URL")
                    
                    # Extract chapter from URL structure
                    chapter_info = self._extract_chapter_from_url(url)
                    chapter_name = chapter_info['chapter']
                    
                    # Group URLs by chapter
                    if chapter_name not in chapter_urls:
                        chapter_urls[chapter_name] = []
                    chapter_urls[chapter_name].append({
                        'url': url,
                        'order': chapter_info['order'],
                        'title': chapter_info['title']
                    })
                    
                    self.discovered_urls.add(url)
                    urls_found += 1
            
            # Process URLs in chapter order
            for chapter_name, urls in chapter_urls.items():
                # Sort URLs within chapter by their path depth and name
                urls.sort(key=lambda x: (x['order'], x['url']))
                
                for i, url_info in enumerate(urls):
                    self.chapter_order[url_info['url']] = i
                    yield Request(
                        url_info['url'],
                        callback=self.parse_page,
                        meta={
                            "depth": response.meta.get("depth", 0),
                            "chapter": chapter_name,
                            "chapter_order": i
                        }
                    )
            
            # Store chapter information
            self.chapters = {name: len(urls) for name, urls in chapter_urls.items()}
            
            # Write progress info for the backend to read
            try:
                import os
                # Write progress file in the same directory as the manifest (job directory)
                manifest_dir = os.path.dirname(self.manifest_path) if hasattr(self, 'manifest_path') else os.getcwd()
                progress_file = os.path.join(manifest_dir, "progress.json")
                progress_data = {
                    "pages_found": urls_found,
                    "pages_scraped": 0,
                    "files_created": 0,
                    "sitemap_processed": True
                }
                self.logger.info(f"DEBUG: About to write progress file to {progress_file}")
                self.logger.info(f"DEBUG: Manifest path: {self.manifest_path}")
                self.logger.info(f"DEBUG: Manifest dir: {manifest_dir}")
                with open(progress_file, 'w', encoding='utf-8') as f:
                    import json
                    json.dump(progress_data, f, indent=2)
                self.logger.info(f"✅ PROGRESS FILE WRITTEN: {progress_file} with {urls_found} pages found")
            except Exception as e:
                self.logger.error(f"❌ FAILED TO WRITE PROGRESS FILE: {e}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Log detailed statistics
            self.logger.info(f"=== SITEMAP PROCESSING COMPLETE ===")
            self.logger.info(f"Total URLs in sitemap: {len(all_url_elements)}")
            self.logger.info(f"URLs skipped (not in scope): {urls_skipped_scope}")
            self.logger.info(f"URLs skipped (not documentation): {urls_skipped_not_doc}")
            self.logger.info(f"URLs skipped (duplicates): {urls_skipped_duplicate}")
            self.logger.info(f"URLs ACCEPTED for scraping: {urls_found}")
            self.logger.info(f"Chapters created: {len(chapter_urls)}")
            
            if urls_found > 0:
                for chapter, urls in chapter_urls.items():
                    self.logger.info(f"  Chapter '{chapter}': {len(urls)} pages")
                    if len(urls) <= 3:  # Show URLs for small chapters
                        for url_info in urls:
                            self.logger.info(f"    -> {url_info['url']}")
            else:
                self.logger.warning("NO URLS FOUND TO SCRAPE!")
                self.logger.warning(f"Base URL pattern: {self.base_url}")
                self.logger.warning("Check _in_scope() and _is_documentation_url() logic")
            
        except ElementTree.ParseError as e:
            self.logger.error(f"Could not parse sitemap XML: {response.url}")
            self.logger.error(f"XML Parse Error: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error parsing sitemap: {response.url}")
            self.logger.error(f"Error: {e}")
    
    def _extract_chapter_from_url(self, url):
        """Extract chapter information from URL structure - generic implementation"""
        parsed = urlparse(url)
        path_parts = [part for part in parsed.path.split('/') if part]
        
        # Default values
        chapter = "Other"
        order = 999
        title = ""
        
        # Look for docs section and extract chapter
        try:
            # Find any documentation base path
            doc_bases = ['docs', 'documentation', 'guide', 'guides', 'api', 'reference', 'manual', 'help']
            docs_index = -1
            
            for i, part in enumerate(path_parts):
                if part.lower() in doc_bases:
                    docs_index = i
                    break
            
            if docs_index >= 0 and len(path_parts) > docs_index + 1:
                # First segment after docs becomes the chapter
                chapter_slug = path_parts[docs_index + 1]
                chapter = self._format_slug_to_title(chapter_slug)
                
                # Order based on alphabetical + common patterns
                order = self._get_generic_order(chapter_slug)
                
                # Title from the deepest path segment or chapter name
                if len(path_parts) > docs_index + 2:
                    title = self._format_slug_to_title(path_parts[-1])
                else:
                    title = chapter  # Chapter overview page
                    
        except (ValueError, IndexError):
            pass
            
        return {
            'chapter': chapter,
            'order': order, 
            'title': title
        }
    
    def _format_slug_to_title(self, slug):
        """Convert URL slug to readable title - generic implementation"""
        # Handle common abbreviations and patterns
        replacements = {
            'api': 'API',
            'sdk': 'SDK', 
            'ui': 'UI',
            'cli': 'CLI',
            'url': 'URL',
            'http': 'HTTP',
            'https': 'HTTPS',
            'json': 'JSON',
            'xml': 'XML'
        }
        
        # Split by hyphens and underscores, then title case
        words = re.split(r'[-_]', slug.lower())
        title_words = []
        
        for word in words:
            if word in replacements:
                title_words.append(replacements[word])
            else:
                title_words.append(word.capitalize())
                
        return ' '.join(title_words)
    
    def _get_generic_order(self, slug):
        """Get order number based on common documentation patterns"""
        # Common documentation ordering patterns
        priority_patterns = {
            'introduction': 1,
            'intro': 1, 
            'overview': 2,
            'getting-started': 3,
            'quickstart': 3,
            'installation': 4,
            'setup': 4,
            'basics': 5,
            'fundamentals': 5,
            'guide': 10,
            'guides': 10,
            'tutorial': 15,
            'tutorials': 15,
            'examples': 20,
            'advanced': 50,
            'api': 60,
            'reference': 70,
            'cli': 75,
            'configuration': 80,
            'troubleshooting': 90,
            'faq': 95,
            'changelog': 98,
            'migration': 99
        }
        
        slug_lower = slug.lower()
        
        # Check for exact matches first
        if slug_lower in priority_patterns:
            return priority_patterns[slug_lower]
            
        # Check for partial matches
        for pattern, order in priority_patterns.items():
            if pattern in slug_lower:
                return order
                
        # Default: alphabetical order offset
        return 500 + ord(slug_lower[0]) if slug_lower else 999
    
    
    def _is_documentation_url(self, url):
        """Check if URL looks like documentation"""
        
        # We are only interested in URLs that contain '/docs/'
        return '/docs/' in url.lower()

    def _in_scope(self, url):
        """Check if URL is within the defined scope (auto-generated from base URL)"""
        # Add detailed logging for debugging - but only for first few URLs
        if not hasattr(self, '_scope_log_count'):
            self._scope_log_count = 0
        
        # Simple check: URL must start with base URL
        if not url.startswith(self.base_url):
            if self._scope_log_count < 10:
                self.logger.info(f"_in_scope({url}) -> False (doesn't start with base URL: {self.base_url})")
                self._scope_log_count += 1
            return False
            
        # For this simplified spider, the only scope rule is that it must be a doc URL.
        # The base URL itself doesn't have to be a doc URL, but the target URL must be.
        url_is_doc = self._is_documentation_url(url)
        if self._scope_log_count < 10:
            self.logger.info(f"_in_scope({url}) -> {url_is_doc} (URL contains '/docs/')")
            self._scope_log_count += 1
        return url_is_doc

    def _update_scraped_progress(self):
        """Update progress file with scraped pages count"""
        self.pages_scraped_count += 1
        try:
            import os
            manifest_dir = os.path.dirname(self.manifest_path) if hasattr(self, 'manifest_path') else os.getcwd()
            progress_file = os.path.join(manifest_dir, "progress.json")
            
            # Read existing progress file if it exists
            progress_data = {
                "pages_found": 0,
                "pages_scraped": self.pages_scraped_count,
                "files_created": 0,
                "sitemap_processed": True
            }
            
            if os.path.exists(progress_file):
                try:
                    with open(progress_file, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                        progress_data.update(existing_data)
                        progress_data["pages_scraped"] = self.pages_scraped_count
                except Exception:
                    pass
            
            # Write updated progress
            with open(progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, indent=2)
                
        except Exception as e:
            self.logger.warning(f"Failed to update progress: {e}")

    def _now(self):
        """Get current timestamp in ISO format"""
        return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

    def _hash_content(self, html):
        """Generate hash of HTML content for change detection"""
        if not html:
            return ""
        # Normalize whitespace and generate hash
        normalized = re.sub(r'\s+', ' ', html.strip())
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]