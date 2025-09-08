import json
import os
import threading
import time
from pathlib import Path


class ProgressTrackerPipeline:
    """
    Optimized progress tracking pipeline that updates spider stats in memory
    instead of writing files to disk for better performance.
    """
    
    def __init__(self):
        self.pages_scraped = 0
        self.files_created = 0
        self.pages_found = 0
        self.sitemap_processed = False
        self.manifest_path = None
        self._lock = threading.RLock()  # Thread-safe updates
        
    def open_spider(self, spider):
        """Initialize progress tracking for the spider."""
        self.spider = spider
        self.manifest_path = getattr(spider, 'manifest_path', None)
        
        # Get pages_found from spider stats if available
        if hasattr(spider.crawler.stats, 'get_value'):
            self.pages_found = spider.crawler.stats.get_value('pages_found', 0)
            self.sitemap_processed = spider.crawler.stats.get_value('sitemap_processed', False)
        
        # Initialize spider stats
        self._update_spider_stats()
        
    def process_item(self, item, spider):
        """Track item processing with minimal overhead."""
        if item.get('md'):
            with self._lock:
                self.pages_scraped += 1
                
                # Update stats from spider crawler
                if hasattr(spider.crawler.stats, 'get_value'):
                    # Get latest pages found (might be updated after sitemap processing)
                    current_pages_found = spider.crawler.stats.get_value('pages_found', 0)
                    if current_pages_found > self.pages_found:
                        self.pages_found = current_pages_found
                    
                    # Check sitemap processing status
                    self.sitemap_processed = spider.crawler.stats.get_value('sitemap_processed', False)
                    
                    # Check if we have the file creation count from AssemblePipeline
                    files_from_stats = spider.crawler.stats.get_value('files_created', 0)
                    if files_from_stats > 0:
                        self.files_created = files_from_stats
                
                # Update spider stats immediately
                self._update_spider_stats()
        
        return item
    
    def close_spider(self, spider):
        """Write final progress on spider close."""
        # Update final stats from spider crawler
        if hasattr(spider.crawler.stats, 'get_value'):
            # Get latest pages found
            current_pages_found = spider.crawler.stats.get_value('pages_found', 0)
            if current_pages_found > self.pages_found:
                self.pages_found = current_pages_found
            
            # Update sitemap processing status
            self.sitemap_processed = spider.crawler.stats.get_value('sitemap_processed', False)
            
            # Get final file count from AssemblePipeline
            files_from_stats = spider.crawler.stats.get_value('files_created', 0)
            if files_from_stats > 0:
                self.files_created = files_from_stats
        
        # Final stats update
        self._update_spider_stats()
    
    def _update_spider_stats(self):
        """Update spider stats in memory and notify CLI if callback exists."""
        if not hasattr(self.spider, 'crawler') or not hasattr(self.spider.crawler, 'stats'):
            return
            
        with self._lock:
            # Update all progress stats in spider memory
            self.spider.crawler.stats.set_value('progress_pages_found', self.pages_found)
            self.spider.crawler.stats.set_value('progress_pages_scraped', self.pages_scraped)
            self.spider.crawler.stats.set_value('progress_files_created', self.files_created)
            self.spider.crawler.stats.set_value('progress_sitemap_processed', self.sitemap_processed)
            
            # Update CLI progress if callback exists
            self._update_cli_progress()
            
            # Write minimal status file for legacy compatibility (if manifest_path exists)
            if self.manifest_path:
                self._write_minimal_status()
    
    def _update_cli_progress(self):
        """Update CLI progress display if callback exists"""
        if not hasattr(self.spider, '_cli_progress_callback'):
            return
        
        progress_callback = self.spider._cli_progress_callback
        
        # Update discovery phase
        if self.pages_found > 0 and self.pages_scraped == 0:
            if hasattr(progress_callback, 'update_discovery'):
                progress_callback.update_discovery(self.pages_found)
        
        # Update scraping phase
        elif self.pages_scraped > 0:
            if hasattr(progress_callback, 'update_scraping'):
                progress_callback.update_scraping(self.pages_scraped)
        
        # Update conversion phase
        if self.files_created > 0:
            if hasattr(progress_callback, 'update_conversion'):
                progress_callback.update_conversion(self.files_created)
    
    def _write_minimal_status(self):
        """Write minimal status file for cross-process monitoring."""
        if not self.manifest_path:
            return
            
        try:
            manifest_dir = os.path.dirname(self.manifest_path)
            status_file = os.path.join(manifest_dir, "status.json")
            
            # Only essential data, no complex formatting
            status_data = {
                "pages_found": self.pages_found,
                "pages_scraped": self.pages_scraped,
                "files_created": self.files_created,
                "sitemap_processed": self.sitemap_processed
            }
            
            # Write directly, no temp file needed for this tiny file
            with open(status_file, 'w') as f:
                json.dump(status_data, f)
                
        except Exception as e:
            # Silently fail to avoid spider disruption
            pass