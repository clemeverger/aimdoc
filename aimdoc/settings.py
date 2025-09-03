BOT_NAME = 'aimdoc'

SPIDER_MODULES = ['aimdoc.spiders']
NEWSPIDER_MODULE = 'aimdoc.spiders'

# Obey robots.txt rules
ROBOTSTXT_OBEY = True

# Configure middlewares
DOWNLOADER_MIDDLEWARES = {}

# Configure item pipelines
ITEM_PIPELINES = {
    'aimdoc.pipelines.optimized_html_markdown.OptimizedHtmlMarkdownPipeline': 150,
    'aimdoc.pipelines.progress_tracker.ProgressTrackerPipeline': 250,  # Before AssemblePipeline
    'aimdoc.pipelines.assemble.AssemblePipeline': 300,
    'aimdoc.pipelines.diff.DiffPipeline': 400,
}

# Enable HTTP caching
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 3600 * 24  # 24 hours
HTTPCACHE_DIR = 'httpcache'
HTTPCACHE_IGNORE_HTTP_CODES = [301, 302, 303, 304, 307, 308]
HTTPCACHE_STORAGE = 'scrapy.extensions.httpcache.FilesystemCacheStorage'

# Enable AutoThrottle with optimized settings
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 0.5  # Reduced from 1 second
AUTOTHROTTLE_MAX_DELAY = 5      # Reduced from 10 seconds  
AUTOTHROTTLE_TARGET_CONCURRENCY = 4.0  # Increased from 2.0
AUTOTHROTTLE_DEBUG = False

# Increase concurrent requests for better performance
CONCURRENT_REQUESTS = 16        # Increased from 8
CONCURRENT_REQUESTS_PER_DOMAIN = 8  # Increased from 4

# Deltafetch middleware not implemented - disabled
DELTAFETCH_ENABLED = False

# Configure user agent
USER_AGENT = 'aimdoc (+https://github.com/your-org/aimdoc)'

# Optimized download delay for faster scraping
DOWNLOAD_DELAY = 0.25           # Reduced from 0.5
RANDOMIZE_DOWNLOAD_DELAY = 0.25 # Reduced from 0.5

# Configure feeds - disabled, handled by AssemblePipeline
FEEDS = {}