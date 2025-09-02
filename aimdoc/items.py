import scrapy


class DocPage(scrapy.Item):
    url = scrapy.Field()
    status = scrapy.Field()
    fetched_at = scrapy.Field()
    etag = scrapy.Field()
    last_modified = scrapy.Field()
    title = scrapy.Field()
    html = scrapy.Field()
    md = scrapy.Field()
    order = scrapy.Field()  # position selon sidebar
    hash = scrapy.Field()   # hash du HTML nettoyé