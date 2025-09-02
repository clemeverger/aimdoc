import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set
from urllib.parse import urlparse


class DiffPipeline:
    """Pipeline to track changes and generate changelog.md per domain"""
    
    def __init__(self):
        self.build_dir = Path('build')
        
        self.current_sources_by_domain = {}  # domain -> {url: item}
        self.previous_sources_by_domain = {}  # domain -> {url: item}
        self.changes_by_domain = {}  # domain -> changes dict

    def open_spider(self, spider):
        """Load previous sources data if available for each domain"""
        self.spider = spider
        
        # Load previous sources data for each domain
        for domain_dir in self.build_dir.iterdir():
            if domain_dir.is_dir():
                domain = domain_dir.name
                sources_file = domain_dir / 'sources.json'
                
                if sources_file.exists():
                    try:
                        with open(sources_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            if 'sources' in data:
                                self.previous_sources_by_domain[domain] = {
                                    source['url']: source 
                                    for source in data['sources']
                                }
                                spider.logger.info(f"Loaded {len(self.previous_sources_by_domain[domain])} previous sources for domain {domain}")
                    except (json.JSONDecodeError, FileNotFoundError) as e:
                        spider.logger.warning(f"Could not load previous sources for {domain}: {e}")

    def process_item(self, item, spider):
        """Track current items for comparison by domain"""
        if item.get('url'):
            # Extract domain from URL
            domain = self._extract_domain_from_url(item['url'])
            
            if domain not in self.current_sources_by_domain:
                self.current_sources_by_domain[domain] = {}
            
            self.current_sources_by_domain[domain][item['url']] = dict(item)
        return item
    
    def _extract_domain_from_url(self, url):
        """Extract domain principal from URL - same logic as AssemblePipeline"""
        parsed = urlparse(url)
        hostname = parsed.netloc.split(':')[0]
        parts = hostname.split('.')
        
        if len(parts) < 2:
            return hostname.lower()
        
        # Remove common prefixes
        prefixes_to_remove = ['www', 'docs', 'api', 'blog', 'help', 'support']
        if parts[0].lower() in prefixes_to_remove and len(parts) > 2:
            parts = parts[1:]
        
        # Get domain without extension
        domain_name = parts[0]
        
        # Clean domain name for filesystem
        import re
        domain_name = re.sub(r'[^a-zA-Z0-9\-_]', '-', domain_name)
        
        return domain_name.lower()

    def close_spider(self, spider):
        """Generate changelog for each domain"""
        
        if not self.current_sources_by_domain:
            spider.logger.warning("No current sources to compare")
            return
        
        # Process each domain
        for domain in self.current_sources_by_domain:
            # Perform diff analysis for this domain
            self._analyze_changes_for_domain(domain)
            
            # Generate changelog for this domain
            self._generate_changelog_for_domain(domain)
            
            # Log summary for this domain
            self._log_change_summary_for_domain(domain)

    def _analyze_changes_for_domain(self, domain):
        """Analyze changes for a specific domain"""
        
        current_sources = self.current_sources_by_domain.get(domain, {})
        previous_sources = self.previous_sources_by_domain.get(domain, {})
        
        changes = {
            'added': [],
            'modified': [],
            'removed': [],
            'unchanged': []
        }
        
        current_urls = set(current_sources.keys())
        previous_urls = set(previous_sources.keys())
        
        # Find added URLs
        added_urls = current_urls - previous_urls
        for url in added_urls:
            changes['added'].append({
                'url': url,
                'title': current_sources[url].get('title', ''),
                'status': 'new'
            })
        
        # Find removed URLs
        removed_urls = previous_urls - current_urls
        for url in removed_urls:
            changes['removed'].append({
                'url': url,
                'title': previous_sources[url].get('title', ''),
                'status': 'removed'
            })
        
        # Find common URLs and check for modifications
        common_urls = current_urls & previous_urls
        for url in common_urls:
            current = current_sources[url]
            previous = previous_sources[url]
            
            change_detected = self._detect_content_change(current, previous)
            
            if change_detected:
                changes['modified'].append({
                    'url': url,
                    'title': current.get('title', ''),
                    'changes': change_detected
                })
            else:
                changes['unchanged'].append({
                    'url': url,
                    'title': current.get('title', '')
                })
        
        self.changes_by_domain[domain] = changes

    def _detect_content_change(self, current: Dict, previous: Dict) -> List[str]:
        """Detect what changed between two versions of a page"""
        changes = []
        
        # Check content hash
        current_hash = current.get('hash', '')
        previous_hash = previous.get('hash', '')
        if current_hash and previous_hash and current_hash != previous_hash:
            changes.append('content')
        
        # Check title
        if current.get('title', '') != previous.get('title', ''):
            changes.append('title')
        
        # Check HTTP status
        if current.get('status') != previous.get('status'):
            changes.append('status')
        
        # Check ETag (if available)
        current_etag = current.get('etag', '')
        previous_etag = previous.get('etag', '')
        if current_etag and previous_etag and current_etag != previous_etag:
            if 'content' not in changes:  # Don't duplicate if hash already detected change
                changes.append('etag')
        
        # Check Last-Modified (if available and no other changes detected)
        if not changes:
            current_modified = current.get('last_modified', '')
            previous_modified = previous.get('last_modified', '')
            if current_modified and previous_modified and current_modified != previous_modified:
                changes.append('last_modified')
        
        return changes

    def _generate_changelog_for_domain(self, domain):
        """Generate changelog.md for a specific domain"""
        
        domain_dir = self.build_dir / domain
        domain_dir.mkdir(parents=True, exist_ok=True)
        changelog_file = domain_dir / 'changelog.md'
        
        changelog_content = self._build_changelog_content_for_domain(domain)
        
        # Read existing changelog if it exists
        existing_changelog = ''
        if changelog_file.exists():
            try:
                with open(changelog_file, 'r', encoding='utf-8') as f:
                    existing_content = f.read()
                    # Keep everything after the first entry
                    lines = existing_content.split('\n')
                    if len(lines) > 10:  # Skip header and first entry
                        # Find the next version marker
                        for i, line in enumerate(lines[10:], 10):
                            if line.startswith('## '):
                                existing_changelog = '\n'.join(lines[i:])
                                break
            except Exception as e:
                self.spider.logger.warning(f"Could not read existing changelog for {domain}: {e}")
        
        # Combine new and existing changelog
        full_changelog = changelog_content
        if existing_changelog:
            full_changelog += '\n' + existing_changelog
        
        # Write changelog
        with open(changelog_file, 'w', encoding='utf-8') as f:
            f.write(full_changelog)
        
        self.spider.logger.info(f"Generated changelog: {domain}/changelog.md")

    def _build_changelog_content_for_domain(self, domain) -> str:
        """Build the changelog content for this domain"""
        
        changes = self.changes_by_domain.get(domain, {})
        current_sources = self.current_sources_by_domain.get(domain, {})
        
        now = datetime.now(timezone.utc)
        version = self._generate_version_for_domain(domain)
        timestamp = now.strftime('%Y-%m-%d %H:%M:%S UTC')
        
        lines = [
            f'# Changelog - {domain}',
            '',
            f'## {version} - {timestamp}',
            ''
        ]
        
        # Summary
        total_changes = len(changes.get('added', [])) + len(changes.get('modified', [])) + len(changes.get('removed', []))
        lines.extend([
            '### Summary',
            '',
            f'- **Total pages:** {len(current_sources)}',
            f'- **Changes:** {total_changes}',
            f'  - Added: {len(changes.get("added", []))}',
            f'  - Modified: {len(changes.get("modified", []))}', 
            f'  - Removed: {len(changes.get("removed", []))}',
            f'  - Unchanged: {len(changes.get("unchanged", []))}',
            ''
        ])
        
        # Added pages
        if changes.get('added'):
            lines.extend([
                '### Added Pages',
                ''
            ])
            for item in changes['added']:
                title = item['title'] or 'Untitled'
                lines.append(f'- [{title}]({item["url"]})')
            lines.append('')
        
        # Modified pages
        if changes.get('modified'):
            lines.extend([
                '### Modified Pages',
                ''
            ])
            for item in changes['modified']:
                title = item['title'] or 'Untitled'
                changes_desc = ', '.join(item['changes'])
                lines.append(f'- [{title}]({item["url"]}) - {changes_desc}')
            lines.append('')
        
        # Removed pages
        if changes.get('removed'):
            lines.extend([
                '### Removed Pages',
                ''
            ])
            for item in changes['removed']:
                title = item['title'] or 'Untitled'
                lines.append(f'- [{title}]({item["url"]})')
            lines.append('')
        
        # Add separator for next entry
        lines.extend(['---', ''])
        
        return '\n'.join(lines)

    def _generate_version_for_domain(self, domain) -> str:
        """Generate version string for this domain build"""
        now = datetime.now()
        base_version = now.strftime('%Y.%m.%d')
        
        domain_dir = self.build_dir / domain
        changelog_file = domain_dir / 'changelog.md'
        
        # Check existing changelog for today's builds
        if changelog_file.exists():
            try:
                with open(changelog_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Count today's versions
                import re
                today_versions = re.findall(rf'^## ({re.escape(base_version)}(?:-\d+)?) - ', content, re.MULTILINE)
                
                if today_versions:
                    # Find highest sequence number
                    max_seq = 0
                    for version in today_versions:
                        if '-' in version:
                            seq = int(version.split('-')[-1])
                            max_seq = max(max_seq, seq)
                    
                    return f'{base_version}-{max_seq + 1}'
            except Exception:
                pass
        
        return base_version

    def _log_change_summary_for_domain(self, domain):
        """Log a summary of changes for a domain"""
        changes = self.changes_by_domain.get(domain, {})
        
        added_count = len(changes.get('added', []))
        modified_count = len(changes.get('modified', []))
        removed_count = len(changes.get('removed', []))
        unchanged_count = len(changes.get('unchanged', []))
        
        self.spider.logger.info(
            f"Change summary for {domain}: +{added_count} ~{modified_count} -{removed_count} ={unchanged_count}"
        )
        
        if added_count > 0:
            self.spider.logger.info(f"Added pages ({domain}): {', '.join(item['url'] for item in changes['added'][:5])}{'...' if added_count > 5 else ''}")
        
        if modified_count > 0:
            self.spider.logger.info(f"Modified pages ({domain}): {', '.join(item['url'] for item in changes['modified'][:5])}{'...' if modified_count > 5 else ''}")
        
        if removed_count > 0:
            self.spider.logger.info(f"Removed pages ({domain}): {', '.join(item['url'] for item in changes['removed'][:5])}{'...' if removed_count > 5 else ''}")