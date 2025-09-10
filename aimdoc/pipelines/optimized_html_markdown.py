import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup, Comment
import markdownify
from datetime import datetime, timezone


class OptimizedHtmlMarkdownPipeline:
    """Optimized pipeline that combines HTML cleaning and markdown conversion in one pass"""
    
    def __init__(self):
        # Selectors for elements to remove (header, footer, nav, etc.)
        self.remove_selectors = [
            'header', 'footer', 'nav', '.nav', '#nav',
            '.header', '.footer', '.navigation', '.navbar',
            '.breadcrumb', '.breadcrumbs',
            '.sidebar-toggle', '.menu-toggle',
            '.advertisement', '.ads', '.ad',
            '.popup', '.modal', '.overlay',
            '.social-share', '.social-sharing',
            '.comment-form', '.comments',
            '.edit-page', '.edit-link',
            '.github-link', '.edit-on-github',
            '.back-to-top',
            'script', 'style', 'noscript',
            '.search-box', '.search-form',
            '.table-of-contents.mobile',  # Keep desktop TOC, remove mobile
        ]
        
        # Selectors for elements that commonly contain noise
        self.noise_classes = [
            'mobile-only', 'desktop-only', 'print-only',
            'visually-hidden', 'sr-only',
            'beta', 'alpha', 'experimental',
            'deprecated', 'legacy'
        ]
        
        # Configure markdownify options
        self.md_options = {
            'heading_style': markdownify.ATX,  # Use # for headings
            'bullets': '-',  # Use - for bullets
            'strip': ['script', 'style'],
            'convert_charrefs': True,
            'escape_asterisks': False,
            'escape_underscores': False,
        }
        
        # Pre-compile regex patterns for performance
        self._compiled_regexes = {
            'whitespace': re.compile(r'\s+'),
            'heading_match': re.compile(r'^(#{1,6})\s+(.+)'),
            'admonition_type': re.compile(r'^\*\*\w+:\*\*'),
            'code_block_restore': re.compile(r'<div data-markdown-code-block="[^"]*">(.*?)</div>', re.DOTALL),
            'image_restore': re.compile(r'<span data-markdown-image="true">(.*?)</span>', re.DOTALL),
            'excessive_newlines': re.compile(r'\n{3,}'),
            'language_patterns': [
                re.compile(r'language-(\w+)'),
                re.compile(r'lang-(\w+)'), 
                re.compile(r'highlight-(\w+)'),
                re.compile(r'^(\w+)$')  # Simple language names
            ]
        }
    
    def process_item(self, item, spider):
        """Process HTML item in one pass - clean and convert to markdown"""
        spider.logger.info(f"OptimizedHtmlMarkdownPipeline processing: {item.get('url', 'unknown')}")
        spider.logger.info(f"  HTML content length: {len(item.get('html', ''))}")
        
        if not item.get('html'):
            spider.logger.warning(f"  No HTML content found, setting empty markdown")
            item['md'] = ''
            return item
            
        # Single HTML parsing - parse only once
        soup = BeautifulSoup(item['html'], 'html.parser')
        
        # Phase 1: Clean HTML (remove unwanted elements)
        self._remove_unwanted_elements(soup)
        
        # Phase 2: Normalize structure for better markdown
        self._normalize_structure(soup)
        
        # Phase 3: Convert relative URLs to absolute
        self._absolutify_urls(soup, item['url'])
        
        # Phase 4: Preprocess for markdown conversion
        self._preprocess_for_markdown(soup)
        
        # Phase 5: Convert to markdown
        html_content = str(soup)
        markdown_content = markdownify.markdownify(html_content, **self.md_options)
        
        # Phase 6: Post-process markdown
        markdown_content = self._postprocess_markdown(markdown_content, item['url'])
        
        # Update both fields
        item['html'] = html_content  # Store cleaned HTML
        item['md'] = markdown_content
        
        spider.logger.info(f"  Markdown content length: {len(markdown_content)}")
        spider.logger.info(f"  Successfully converted HTML to markdown")
        
        return item

    def _remove_unwanted_elements(self, soup):
        """Remove navigation, headers, footers, and other unwanted elements"""
        
        # Remove elements by selector
        for selector in self.remove_selectors:
            elements = soup.select(selector)
            for element in elements:
                element.decompose()
        
        # Remove elements with noise classes
        for class_name in self.noise_classes:
            elements = soup.select(f'.{class_name}')
            for element in elements:
                element.decompose()
        
        # Remove HTML comments
        comments = soup.find_all(string=lambda text: isinstance(text, Comment))
        for comment in comments:
            comment.extract()
        
        # Remove empty paragraphs and divs
        for tag_name in ['p', 'div', 'span']:
            elements = soup.find_all(tag_name)
            for element in elements:
                if not element.get_text(strip=True) and not element.find(['img', 'svg', 'iframe']):
                    element.decompose()

    def _normalize_structure(self, soup):
        """Normalize HTML structure for better markdown conversion"""
        
        # Fix heading hierarchy - ensure no jumps (h1->h3 without h2)
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        if headings:
            # Start from h2 if we have h1, otherwise from h1
            current_level = 2 if soup.find('h1') else 1
            
            for heading in headings[1:]:  # Skip first heading
                heading_level = int(heading.name[1])
                
                # Don't allow jumps of more than 1 level
                if heading_level > current_level + 1:
                    new_level = current_level + 1
                    heading.name = f'h{new_level}'
                    current_level = new_level
                else:
                    current_level = heading_level
        
        # Normalize code blocks
        self._normalize_code_blocks(soup)
        
        # Normalize admonitions (Note, Warning, etc.)
        self._normalize_admonitions(soup)
        
        # Clean up whitespace in text nodes (use pre-compiled regex)
        for text_node in soup.find_all(string=True):
            if text_node.parent.name not in ['pre', 'code']:
                normalized = self._compiled_regexes['whitespace'].sub(' ', text_node).strip()
                text_node.replace_with(normalized)

    def _normalize_code_blocks(self, soup):
        """Normalize code blocks for better markdown conversion"""
        
        # Handle various code block patterns
        code_selectors = [
            'pre code',
            'pre.highlight',
            '.highlight pre',
            '.code-block pre',
            '.codehilite pre'
        ]
        
        for selector in code_selectors:
            elements = soup.select(selector)
            for element in elements:
                # Extract language from class names
                language = self._extract_language(element)
                
                # Ensure proper structure: <pre><code class="language-xxx">
                if element.name == 'code' and element.parent.name == 'pre':
                    pre = element.parent
                    code = element
                else:
                    pre = element
                    code = pre.find('code')
                    if not code:
                        # Wrap content in code tag
                        content = pre.get_text()
                        pre.clear()
                        code = soup.new_tag('code')
                        code.string = content
                        pre.append(code)
                
                # Set language class
                if language:
                    code['class'] = code.get('class', []) + [f'language-{language}']
                
                # Clean up parent classes
                pre['class'] = ['highlight'] if language else []

    def _extract_language(self, element):
        """Extract programming language from element classes using pre-compiled patterns"""
        classes = []
        
        # Check element and its parents for language indicators
        for elem in [element, element.parent, element.find_parent()]:
            if elem and elem.get('class'):
                classes.extend(elem.get('class', []))
        
        # Use pre-compiled regex patterns for performance
        for class_name in classes:
            for pattern in self._compiled_regexes['language_patterns']:
                match = pattern.match(class_name)
                if match:
                    lang = match.group(1).lower()
                    # Map some common aliases
                    lang_map = {
                        'js': 'javascript',
                        'ts': 'typescript',
                        'py': 'python',
                        'rb': 'ruby',
                        'sh': 'bash'
                    }
                    return lang_map.get(lang, lang)
        
        return None

    def _normalize_admonitions(self, soup):
        """Convert various admonition formats to a standard blockquote format"""
        
        # Common admonition selectors
        admonition_selectors = [
            '.admonition', '.note', '.warning', '.tip', '.info',
            '.alert', '.callout', '.highlight-note', '.highlight-warning',
            '[class*="admonition"]', '[class*="alert-"]'
        ]
        
        for selector in admonition_selectors:
            elements = soup.select(selector)
            for element in elements:
                # Determine admonition type
                admonition_type = self._get_admonition_type(element)
                
                # Convert to blockquote format
                blockquote = soup.new_tag('blockquote')
                
                # Add type as strong text
                if admonition_type:
                    type_elem = soup.new_tag('strong')
                    type_elem.string = f"{admonition_type.title()}: "
                    blockquote.append(type_elem)
                
                # Move content
                for child in list(element.children):
                    if child.name == 'p' and child == element.find('p'):
                        # First paragraph - append to same line as type
                        if blockquote.contents:
                            blockquote.contents[-1].append(child.get_text())
                        else:
                            blockquote.append(child.get_text())
                    else:
                        blockquote.append(child)
                
                element.replace_with(blockquote)

    def _get_admonition_type(self, element):
        """Determine the type of admonition from element classes"""
        classes = element.get('class', [])
        
        # Check for explicit type indicators
        type_indicators = ['note', 'warning', 'tip', 'info', 'caution', 'important']
        
        for class_name in classes:
            class_lower = class_name.lower()
            for indicator in type_indicators:
                if indicator in class_lower:
                    return indicator
        
        # Check for Bootstrap alert classes
        for class_name in classes:
            if class_name.startswith('alert-'):
                alert_type = class_name[6:]  # Remove 'alert-' prefix
                type_map = {
                    'info': 'info',
                    'warning': 'warning', 
                    'danger': 'warning',
                    'success': 'tip'
                }
                return type_map.get(alert_type, 'note')
        
        return 'note'  # Default

    def _absolutify_urls(self, soup, base_url):
        """Convert relative URLs to absolute URLs"""
        
        # Process links
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            if href and not href.startswith(('http://', 'https://', 'mailto:', '#')):
                absolute_url = urljoin(base_url, href)
                link['href'] = absolute_url
        
        # Process images
        for img in soup.find_all('img', src=True):
            src = img.get('src')
            if src and not src.startswith(('http://', 'https://', 'data:')):
                absolute_url = urljoin(base_url, src)
                img['src'] = absolute_url

    def _preprocess_for_markdown(self, soup):
        """Preprocess HTML elements for better markdown conversion"""
        
        # Handle code blocks
        self._preprocess_code_blocks(soup)
        
        # Handle tables
        self._preprocess_tables(soup)
        
        # Handle admonitions
        self._preprocess_admonitions(soup)
        
        # Handle images
        self._preprocess_images(soup)

    def _preprocess_code_blocks(self, soup):
        """Ensure code blocks are properly formatted for markdown"""
        
        # Find all code blocks
        code_blocks = soup.find_all('pre')
        
        for pre in code_blocks:
            code = pre.find('code')
            if code:
                # Extract language from class (reuse existing method)
                language = self._extract_code_language(code)
                
                # Get code content
                content = code.get_text()
                
                # Create markdown code block
                if language:
                    markdown_block = f"\n```{language}\n{content}\n```\n"
                else:
                    markdown_block = f"\n```\n{content}\n```\n"
                
                # Replace with a special marker that markdownify won't touch
                marker_id = id(pre)
                marker = soup.new_tag('div', **{'data-markdown-code-block': str(marker_id)})
                marker.string = markdown_block
                pre.replace_with(marker)

    def _extract_code_language(self, code_element):
        """Extract programming language from code element classes"""
        classes = code_element.get('class', [])
        
        for class_name in classes:
            if class_name.startswith('language-'):
                return class_name[9:]  # Remove 'language-' prefix
            elif class_name.startswith('lang-'):
                return class_name[5:]   # Remove 'lang-' prefix
        
        return None

    def _preprocess_tables(self, soup):
        """Ensure tables are preserved properly"""
        tables = soup.find_all('table')
        
        for table in tables:
            # Add border attribute to ensure markdownify recognizes it as a table
            table['border'] = '1'
            
            # Ensure proper table structure
            tbody = table.find('tbody')
            if not tbody:
                # Wrap existing rows in tbody
                rows = table.find_all('tr')
                if rows:
                    tbody = soup.new_tag('tbody')
                    for row in rows:
                        tbody.append(row.extract())
                    table.append(tbody)

    def _preprocess_admonitions(self, soup):
        """Handle admonitions (notes, warnings, etc.) using pre-compiled regex"""
        blockquotes = soup.find_all('blockquote')
        
        for bq in blockquotes:
            # Check if this is an admonition (starts with **Type:**) using pre-compiled regex
            first_text = bq.get_text().strip()
            if self._compiled_regexes['admonition_type'].match(first_text):
                # This is an admonition, preserve it as blockquote
                continue

    def _preprocess_images(self, soup):
        """Handle images for markdown conversion"""
        images = soup.find_all('img')
        
        for img in images:
            src = img.get('src', '')
            alt = img.get('alt', '')
            title = img.get('title', '')
            
            # Create markdown image syntax
            if title:
                markdown_img = f'![{alt}]({src} "{title}")'
            else:
                markdown_img = f'![{alt}]({src})'
            
            # Replace with markdown
            marker = soup.new_tag('span', **{'data-markdown-image': 'true'})
            marker.string = markdown_img
            img.replace_with(marker)

    def _postprocess_markdown(self, markdown_content, source_url):
        """Clean up and enhance the generated markdown using pre-compiled regexes"""
        
        # Restore custom code blocks (use pre-compiled regex)
        markdown_content = self._compiled_regexes['code_block_restore'].sub(
            r'\1', markdown_content
        )
        
        # Restore custom images (use pre-compiled regex)
        markdown_content = self._compiled_regexes['image_restore'].sub(
            r'\1', markdown_content
        )
        
        # Fix heading levels - ensure single # for page title
        lines = markdown_content.split('\n')
        processed_lines = []
        found_first_heading = False
        
        for line in lines:
            # Check if this is a heading (use pre-compiled regex)
            heading_match = self._compiled_regexes['heading_match'].match(line)
            if heading_match:
                level = len(heading_match.group(1))
                title = heading_match.group(2)
                
                if not found_first_heading:
                    # First heading becomes h1
                    processed_lines.append(f'# {title}')
                    found_first_heading = True
                else:
                    # Subsequent headings start at h2
                    new_level = max(2, level)
                    processed_lines.append(f'{"#" * new_level} {title}')
            else:
                processed_lines.append(line)
        
        markdown_content = '\n'.join(processed_lines)
        
        # Clean up excessive whitespace (use pre-compiled regex)
        markdown_content = self._compiled_regexes['excessive_newlines'].sub('\n\n', markdown_content)
        
        # Add source block at the end
        source_block = self._create_source_block(source_url)
        markdown_content = f'{markdown_content.strip()}\n\n{source_block}'
        
        return markdown_content.strip()

    def _create_source_block(self, url):
        """Create source attribution block"""
        timestamp = datetime.now(timezone.utc).isoformat()
        return f'<!-- source: {url} | fetched: {timestamp} -->'