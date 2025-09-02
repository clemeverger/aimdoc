import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup, Comment


class CleanHtmlPipeline:
    """Pipeline to clean HTML content and prepare it for markdown conversion"""
    
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

    def process_item(self, item, spider):
        """Clean HTML content in the item"""
        if not item.get('html'):
            return item
            
        # Parse HTML
        soup = BeautifulSoup(item['html'], 'html.parser')
        
        # Remove unwanted elements
        self._remove_unwanted_elements(soup)
        
        # Clean up attributes and normalize structure  
        self._normalize_structure(soup)
        
        # Convert relative URLs to absolute
        self._absolutify_urls(soup, item['url'])
        
        # Update the cleaned HTML
        item['html'] = str(soup)
        
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
        
        # Clean up whitespace in text nodes
        for text_node in soup.find_all(string=True):
            if text_node.parent.name not in ['pre', 'code']:
                normalized = re.sub(r'\s+', ' ', text_node).strip()
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
        """Extract programming language from element classes"""
        classes = []
        
        # Check element and its parents for language indicators
        for elem in [element, element.parent, element.find_parent()]:
            if elem and elem.get('class'):
                classes.extend(elem.get('class', []))
        
        # Common language class patterns
        language_patterns = [
            r'language-(\w+)',
            r'lang-(\w+)', 
            r'highlight-(\w+)',
            r'^(\w+)$'  # Simple language names
        ]
        
        for class_name in classes:
            for pattern in language_patterns:
                match = re.match(pattern, class_name)
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