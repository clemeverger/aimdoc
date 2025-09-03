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
        
        # Load manifest file
        with open(manifest, 'r', encoding='utf-8') as f:
            self.manifest = json.load(f)
        
        self.since = since
        self.discovered_urls = set()
        self.chapter_order = {}
        self.chapters = {}  # Store chapter information extracted from URLs
        
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
    
    async def start(self):
        """Generate initial requests for automatic discovery (async version)"""
        for url in self.seed_urls:
            if url.endswith('robots.txt'):
                yield Request(
                    url,
                    callback=self._parse_robots,
                    meta={"depth": 0},
                    errback=self._handle_discovery_error
                )
            elif url.endswith(('.xml', 'sitemap')):
                yield Request(
                    url,
                    callback=self._parse_sitemap,
                    meta={"depth": 0},
                    errback=self._handle_discovery_error
                )


    def _parse_robots(self, response):
        """Parse robots.txt to find sitemap URLs"""
        sitemap_urls = []
        
        for line in response.text.split('\n'):
            line = line.strip()
            if line.lower().startswith('sitemap:'):
                sitemap_url = line[8:].strip()
                sitemap_urls.append(sitemap_url)
                
        if sitemap_urls:
            self.logger.info(f"Found {len(sitemap_urls)} sitemap(s) in robots.txt")
            for sitemap_url in sitemap_urls:
                yield Request(
                    sitemap_url,
                    callback=self._parse_sitemap,
                    meta={"depth": 0}
                )
        else:
            self.logger.info("No sitemaps found in robots.txt, trying fallback")
            # Fallback to direct sitemap.xml
            yield Request(
                f"{self.base_url}/sitemap.xml",
                callback=self._parse_sitemap,
                meta={"depth": 0},
                errback=self._handle_discovery_error
            )
    
    def _handle_discovery_error(self, failure):
        """Handle discovery errors gracefully"""
        self.logger.warning(f"Discovery failed for {failure.request.url}: {failure.value}")
        return []

    def parse_page(self, response):
        """Main parsing method for documentation pages"""        
        # Extract page content
        item = self._extract_page_content(response)
        yield item

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
        try:
            root = ElementTree.fromstring(response.body)
            # Handle XML namespace
            namespace = {"": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            
            urls_found = 0
            chapter_urls = {}  # Group URLs by chapter
            
            for url_element in root.findall(".//url", namespace):
                loc_element = url_element.find("loc", namespace)
                if loc_element is not None:
                    url = loc_element.text
                    
                    # Check if URL is in scope and looks like documentation
                    if (self._in_scope(url) and 
                        self._is_documentation_url(url) and 
                        url not in self.discovered_urls):
                        
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
            
            self.logger.info(f"Found {urls_found} documentation URLs in {len(chapter_urls)} chapters")
            for chapter, count in self.chapters.items():
                self.logger.info(f"  - {chapter}: {count} pages")
            
        except ElementTree.ParseError:
            self.logger.warning(f"Could not parse sitemap: {response.url}")
    
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
        doc_patterns = [
            '/docs/', '/documentation/', '/guide/', '/guides/',
            '/api/', '/reference/', '/manual/', '/help/',
            '/tutorial/', '/tutorials/', '/learn/', '/getting-started/'
        ]
        
        url_lower = url.lower()
        return any(pattern in url_lower for pattern in doc_patterns)

    def _in_scope(self, url):
        """Check if URL is within the defined scope (auto-generated from base URL)"""
        # Simple check: URL must start with base URL
        if not url.startswith(self.base_url):
            return False
            
        # If the base URL itself contains documentation patterns, accept all URLs under it
        if self._is_documentation_url(self.base_url):
            return True
            
        # Otherwise, check if the specific URL is a documentation URL
        return self._is_documentation_url(url)

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