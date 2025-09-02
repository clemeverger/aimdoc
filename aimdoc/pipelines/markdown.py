import re
from bs4 import BeautifulSoup
import markdownify


class HtmlToMarkdownPipeline:
    """Pipeline to convert cleaned HTML to markdown"""
    
    def __init__(self):
        # Configure markdownify options
        self.md_options = {
            'heading_style': markdownify.ATX,  # Use # for headings
            'bullets': '-',  # Use - for bullets
            'strip': ['script', 'style'],
            'convert_charrefs': True,
            'escape_asterisks': False,
            'escape_underscores': False,
        }

    def process_item(self, item, spider):
        """Convert HTML to markdown"""
        if not item.get('html'):
            item['md'] = ''
            return item
        
        # Parse HTML for custom processing
        soup = BeautifulSoup(item['html'], 'html.parser')
        
        # Pre-process for better markdown conversion
        self._preprocess_for_markdown(soup)
        
        # Convert to markdown
        html_content = str(soup)
        markdown_content = markdownify.markdownify(
            html_content, 
            **self.md_options
        )
        
        # Post-process markdown
        markdown_content = self._postprocess_markdown(markdown_content, item['url'])
        
        item['md'] = markdown_content
        return item

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
                # Extract language from class
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
        """Handle admonitions (notes, warnings, etc.)"""
        blockquotes = soup.find_all('blockquote')
        
        for bq in blockquotes:
            # Check if this is an admonition (starts with **Type:**)
            first_text = bq.get_text().strip()
            if re.match(r'^\*\*\w+:\*\*', first_text):
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
        """Clean up and enhance the generated markdown"""
        
        # Restore custom code blocks
        markdown_content = re.sub(
            r'<div data-markdown-code-block="[^"]*">(.*?)</div>',
            r'\1',
            markdown_content,
            flags=re.DOTALL
        )
        
        # Restore custom images
        markdown_content = re.sub(
            r'<span data-markdown-image="true">(.*?)</span>',
            r'\1',
            markdown_content,
            flags=re.DOTALL
        )
        
        # Fix heading levels - ensure single # for page title
        lines = markdown_content.split('\n')
        processed_lines = []
        found_first_heading = False
        
        for line in lines:
            # Check if this is a heading
            heading_match = re.match(r'^(#{1,6})\s+(.+)', line)
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
        
        # Clean up excessive whitespace
        markdown_content = re.sub(r'\n{3,}', '\n\n', markdown_content)
        
        # Add source block at the end
        source_block = self._create_source_block(source_url)
        markdown_content = f'{markdown_content.strip()}\n\n{source_block}'
        
        return markdown_content.strip()

    def _create_source_block(self, url):
        """Create source attribution block"""
        from datetime import datetime, timezone
        
        timestamp = datetime.now(timezone.utc).isoformat()
        return f'<!-- source: {url} | fetched: {timestamp} -->'