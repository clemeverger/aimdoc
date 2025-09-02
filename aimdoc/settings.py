BOT_NAME = 'aimdoc'

SPIDER_MODULES = ['aimdoc.spiders']
NEWSPIDER_MODULE = 'aimdoc.spiders'

# Obey robots.txt rules
ROBOTSTXT_OBEY = True

# Configure middlewares
DOWNLOADER_MIDDLEWARES = {}

# Configure item pipelines
ITEM_PIPELINES = {
    'aimdoc.pipelines.clean_html.CleanHtmlPipeline': 100,
    'aimdoc.pipelines.markdown.HtmlToMarkdownPipeline': 200,
    'aimdoc.pipelines.assemble.AssemblePipeline': 300,
    'aimdoc.pipelines.diff.DiffPipeline': 400,
}

# Enable HTTP caching
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 3600 * 24  # 24 hours
HTTPCACHE_DIR = 'httpcache'
HTTPCACHE_IGNORE_HTTP_CODES = [301, 302, 303, 304, 307, 308]
HTTPCACHE_STORAGE = 'scrapy.extensions.httpcache.FilesystemCacheStorage'

# Enable AutoThrottle
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0
AUTOTHROTTLE_DEBUG = False

# Set default concurrent requests
CONCURRENT_REQUESTS = 8
CONCURRENT_REQUESTS_PER_DOMAIN = 4

# Deltafetch middleware not implemented - disabled
DELTAFETCH_ENABLED = False

# Configure user agent
USER_AGENT = 'aimdoc (+https://github.com/your-org/aimdoc)'

# Set download delay
DOWNLOAD_DELAY = 0.5
RANDOMIZE_DOWNLOAD_DELAY = 0.5

# Configure feeds - disabled, handled by AssemblePipeline
FEEDS = {}