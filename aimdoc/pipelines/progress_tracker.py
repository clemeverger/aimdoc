import json
import os
import threading
import time
from pathlib import Path


class ProgressTrackerPipeline:
    """
    Optimized progress tracking pipeline that writes progress.json periodically
    instead of on every item to avoid blocking I/O in the main thread.
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
        
        # Write initial progress file
        self._write_progress_sync()
        
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
                
                # Write progress file immediately (non-blocking)
                self._write_progress_async()
        
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
        
        # Final progress write
        self._write_progress_sync()
        
        # Write scraping summary for the API
        self._write_scraping_summary()
    
    def _write_progress_async(self):
        """Write progress file in a separate thread to avoid blocking."""
        if not self.manifest_path:
            return
            
        # Use a separate thread for I/O
        thread = threading.Thread(target=self._write_progress_sync, daemon=True)
        thread.start()
    
    def _write_progress_sync(self):
        """Write progress file synchronously (called from background thread)."""
        if not self.manifest_path:
            return
            
        try:
            manifest_dir = os.path.dirname(self.manifest_path)
            progress_file = os.path.join(manifest_dir, "progress.json")
            
            with self._lock:
                progress_data = {
                    "pages_found": self.pages_found,
                    "pages_scraped": self.pages_scraped,
                    "files_created": self.files_created,
                    "sitemap_processed": self.sitemap_processed
                }
            
            # Atomic write using temp file
            temp_file = progress_file + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, indent=2)
            
            # Atomic move
            if os.name == 'nt':  # Windows
                if os.path.exists(progress_file):
                    os.remove(progress_file)
            os.rename(temp_file, progress_file)
            
        except Exception as e:
            # Log but don't fail the spider
            if hasattr(self, 'spider') and hasattr(self.spider, 'logger'):
                self.spider.logger.warning(f"Failed to write progress file: {e}")
    
    def _write_scraping_summary(self):
        """Write scraping summary for the API to read final results."""
        if not self.manifest_path:
            return
            
        try:
            manifest_dir = os.path.dirname(self.manifest_path)
            summary_file = os.path.join(manifest_dir, "scraping_summary.json")
            
            # Get failed pages from spider if available
            failed_pages = getattr(self.spider, 'failed_pages', [])
            
            summary_data = {
                "pages_discovered": self.pages_found,
                "pages_scraped": self.pages_scraped,  
                "pages_failed": len(failed_pages),
                "files_created": self.files_created,
                "failed_pages": failed_pages[:10]  # Only store first 10 failed pages
            }
            
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, indent=2)
                
        except Exception as e:
            if hasattr(self, 'spider') and hasattr(self.spider, 'logger'):
                self.spider.logger.warning(f"Failed to write scraping summary: {e}")