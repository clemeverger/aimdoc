import json
import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import urlparse
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

    def __init__(self, manifest, job_dir=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Store manifest path for progress file
        self.manifest_path = manifest
        self.job_dir = job_dir
        
        # Load manifest file
        with open(manifest, 'r', encoding='utf-8') as f:
            self.manifest = json.load(f)
        self.discovered_urls = set()
        self.chapter_order = {}
        self.chapters = {}  # Store chapter information extracted from URLs
        self.pages_scraped_count = 0  # Track scraped pages for progress
        self.failed_pages = []  # Track pages that failed to scrape
        
        # Extract minimal configuration from manifest
        self.name_project = self.manifest.get("name", "aimdoc")
        
        # Get base URL and auto-generate discovery URLs
        base_url = self.manifest.get("url", "")
        if not base_url:
            raise ValueError("Manifest must contain 'url' field")
            
        self.base_url = base_url.rstrip('/')
        self.seed_urls = self._generate_discovery_urls()
        
        # Use hardcoded universal selectors
        self.selectors = {
            "title": "h1, .title, .page-title",
            "content": "main, article, .content, .prose, .markdown-body, .doc-content"
        }
        
        # No custom rate limiting - use Scrapy defaults
        
        # Pre-compile regex patterns for performance optimization
        self._whitespace_pattern = re.compile(r'\s+')

    def _generate_discovery_urls(self):
        """Generate discovery URLs from base URL"""
        return [
            f"{self.base_url}/robots.txt",
            f"{self.base_url}/sitemap.xml",
            f"{self.base_url}/docs/sitemap.xml",
            f"{self.base_url}/sitemap_index.xml"
        ]
    
    async def start(self):
        """Generate initial requests for automatic discovery (async version)"""
        self.logger.info(f"=== SPIDER START ===")
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
        
        # Store discovery failure information for better error reporting
        if not hasattr(self, 'discovery_errors'):
            self.discovery_errors = []
        
        error_info = {
            'url': failure.request.url,
            'error': str(failure.value),
            'error_type': type(failure.value).__name__
        }
        self.discovery_errors.append(error_info)
        
        return []

    def parse_page(self, response):
        """Main parsing method for documentation pages"""
        self.logger.info(f"=== PARSING PAGE: {response.url} ===")
        self.logger.info(f"Status: {response.status}, Size: {len(response.body)} bytes")
        
        # Check for HTTP errors
        if response.status >= 400:
            error_info = {
                'url': response.url,
                'status': response.status,
                'reason': f'HTTP {response.status} error'
            }
            self.failed_pages.append(error_info)
            self.logger.warning(f"❌ Failed to scrape {response.url}: HTTP {response.status}")
            return
        
        # Extract page content
        try:
            item = self._extract_page_content(response)
            self.logger.info(f"Extracted item: title='{item['title']}', content_length={len(item['html'])}")
            
            # Check if we got meaningful content
            if not item['html'] or len(item['html'].strip()) < 100:
                self.logger.warning(f"⚠️ Page {response.url} has very little content: {len(item['html'])} chars")
            
            yield item
            
            # Track scraped pages using Scrapy stats instead of file I/O
            self.pages_scraped_count += 1
            if hasattr(self.crawler.stats, 'inc_value'):
                self.crawler.stats.inc_value('pages_scraped')
        except Exception as e:
            error_info = {
                'url': response.url,
                'status': response.status,
                'reason': f'Parse error: {str(e)}'
            }
            self.failed_pages.append(error_info)
            self.logger.error(f"❌ Failed to parse {response.url}: {str(e)}")

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
        
        # Track detailed filtering statistics
        filtering_stats = {
            'total_urls': 0,
            'skipped_scope': {'count': 0, 'examples': []},
            'skipped_not_doc': {'count': 0, 'examples': []},
            'skipped_duplicate': {'count': 0, 'examples': []},
            'accepted': {'count': 0, 'examples': []}
        }
        
        try:
            root = ElementTree.fromstring(response.body)
            # Handle XML namespace
            namespace = {"": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            
            all_url_elements = root.findall(".//url", namespace)
            filtering_stats['total_urls'] = len(all_url_elements)
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
                    
                    if i < 10:  # Log first 10 URLs for debugging
                        self.logger.info(f"Processing URL #{i+1}: {url}")
                    
                    # Check if URL is in scope
                    in_scope = self._in_scope(url)
                    if not in_scope:
                        urls_skipped_scope += 1
                        filtering_stats['skipped_scope']['count'] += 1
                        if len(filtering_stats['skipped_scope']['examples']) < 5:
                            filtering_stats['skipped_scope']['examples'].append(url)
                        if i < 10:
                            self.logger.info(f"  -> SKIPPED: Not in scope")
                        continue
                    
                    # Check if looks like documentation
                    is_doc = self._is_documentation_url(url)
                    if not is_doc:
                        urls_skipped_not_doc += 1
                        filtering_stats['skipped_not_doc']['count'] += 1
                        if len(filtering_stats['skipped_not_doc']['examples']) < 5:
                            filtering_stats['skipped_not_doc']['examples'].append(url)
                        if i < 10:
                            self.logger.info(f"  -> SKIPPED: Not documentation URL")
                        continue
                    
                    # Check if already discovered
                    if url in self.discovered_urls:
                        urls_skipped_duplicate += 1
                        filtering_stats['skipped_duplicate']['count'] += 1
                        if len(filtering_stats['skipped_duplicate']['examples']) < 5:
                            filtering_stats['skipped_duplicate']['examples'].append(url)
                        if i < 10:
                            self.logger.info(f"  -> SKIPPED: Duplicate URL")
                        continue
                    
                    filtering_stats['accepted']['count'] += 1
                    if len(filtering_stats['accepted']['examples']) < 5:
                        filtering_stats['accepted']['examples'].append(url)
                    
                    if i < 10:
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
            
            # Store progress in Scrapy stats (non-blocking)
            if hasattr(self.crawler.stats, 'set_value'):
                self.crawler.stats.set_value('pages_found', urls_found)
                self.crawler.stats.set_value('sitemap_processed', True)
            self.logger.info(f"✅ SITEMAP PROCESSED: {urls_found} pages found")
            
            # Log detailed statistics with examples
            self.logger.info(f"=== SITEMAP PROCESSING COMPLETE ===")
            self.logger.info(f"Total URLs in sitemap: {filtering_stats['total_urls']}")
            
            # Log skipped URLs with examples
            self.logger.info(f"URLs skipped (not in scope): {filtering_stats['skipped_scope']['count']}")
            if filtering_stats['skipped_scope']['examples']:
                self.logger.info(f"  Examples: {filtering_stats['skipped_scope']['examples']}")
            
            self.logger.info(f"URLs skipped (not documentation): {filtering_stats['skipped_not_doc']['count']}")
            if filtering_stats['skipped_not_doc']['examples']:
                self.logger.info(f"  Examples: {filtering_stats['skipped_not_doc']['examples']}")
            
            self.logger.info(f"URLs skipped (duplicates): {filtering_stats['skipped_duplicate']['count']}")
            if filtering_stats['skipped_duplicate']['examples']:
                self.logger.info(f"  Examples: {filtering_stats['skipped_duplicate']['examples']}")
            
            self.logger.info(f"URLs ACCEPTED for scraping: {filtering_stats['accepted']['count']}")
            if filtering_stats['accepted']['examples']:
                self.logger.info(f"  Examples: {filtering_stats['accepted']['examples']}")
            
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
                
            # Summary validation
            total_processed = (filtering_stats['skipped_scope']['count'] + 
                             filtering_stats['skipped_not_doc']['count'] + 
                             filtering_stats['skipped_duplicate']['count'] + 
                             filtering_stats['accepted']['count'])
            if total_processed != filtering_stats['total_urls']:
                self.logger.warning(f"VALIDATION WARNING: Total processed ({total_processed}) != Total URLs ({filtering_stats['total_urls']})")
            else:
                self.logger.info(f"✓ All {filtering_stats['total_urls']} URLs processed correctly")
            
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
            # Find documentation base path
            doc_bases = ['docs']
            docs_index = -1
            
            for i, part in enumerate(path_parts):
                if part.lower() in doc_bases:
                    docs_index = i
                    break
            
            if docs_index >= 0 and len(path_parts) > docs_index + 1:
                # First segment after docs becomes the chapter
                chapter_slug = path_parts[docs_index + 1]
                chapter = self._format_slug_to_title(chapter_slug)
                
                # Simple alphabetical ordering
                order = ord(chapter_slug.lower()[0]) if chapter_slug else 999
                
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


    def _now(self):
        """Get current timestamp in ISO format"""
        return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

    def _hash_content(self, html):
        """Generate hash of HTML content for change detection"""
        if not html:
            return ""
        # Normalize whitespace and generate hash (use pre-compiled regex)
        normalized = self._whitespace_pattern.sub(' ', html.strip())
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]

    def closed(self, reason):
        """Called when spider closes - log final summary"""
        self.logger.info(f"=== SPIDER CLOSING: {reason} ===")
        self.logger.info(f"Pages discovered: {len(self.discovered_urls)}")
        self.logger.info(f"Pages successfully scraped: {self.pages_scraped_count}")
        self.logger.info(f"Pages failed: {len(self.failed_pages)}")
        
        # Log discovery errors if any
        discovery_errors = getattr(self, 'discovery_errors', [])
        if discovery_errors:
            self.logger.warning(f"❌ DISCOVERY ERRORS ({len(discovery_errors)}):")
            for i, error in enumerate(discovery_errors, 1):
                self.logger.warning(f"  {i}. {error['url']} - {error['error_type']}: {error['error']}")
        
        if self.failed_pages:
            self.logger.warning(f"❌ FAILED PAGES DETAILS:")
            for i, failed in enumerate(self.failed_pages, 1):
                self.logger.warning(f"  {i}. {failed['url']} - {failed['reason']}")
        
        # Calculate the expected vs actual scraping counts
        expected_pages = len(self.discovered_urls)
        actual_scraped = self.pages_scraped_count
        failed_count = len(self.failed_pages)
        
        if actual_scraped + failed_count != expected_pages:
            missing = expected_pages - actual_scraped - failed_count
            self.logger.warning(f"⚠️ DISCREPANCY: {missing} pages unaccounted for")
            self.logger.warning(f"  Expected: {expected_pages}, Scraped: {actual_scraped}, Failed: {failed_count}")
        else:
            self.logger.info(f"✓ All discovered pages accounted for: {expected_pages} total")
        
        # Write final summary to progress file
        try:
            import os
            manifest_dir = os.path.dirname(self.manifest_path) if hasattr(self, 'manifest_path') else os.getcwd()
            summary_file = os.path.join(manifest_dir, "scraping_summary.json")
            
            discovery_errors = getattr(self, 'discovery_errors', [])
            summary_data = {
                "spider_close_reason": reason,
                "pages_discovered": len(self.discovered_urls),
                "pages_scraped": self.pages_scraped_count,
                "pages_failed": len(self.failed_pages),
                "failed_pages": self.failed_pages,
                "discovery_errors": discovery_errors,
                "discovered_urls": list(self.discovered_urls),
                "chapters": self.chapters
            }
            
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, indent=2)
            self.logger.info(f"📄 Summary written to: {summary_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to write scraping summary: {e}")