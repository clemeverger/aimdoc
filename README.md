# aimdoc

**Give your AI the context it needs.** Extract any documentation site into clean, AI-ready Markdown.

## Why aimdoc?

As a developer, you know the struggle:
- 📚 Your AI needs context about frameworks, APIs, and libraries
- 🤖 Copy-pasting docs into ChatGPT is tedious and limited
- 📖 Documentation sites are full of navigation, ads, and noise
- ⚡ You need **clean, structured context** for your AI tools

**aimdoc solves this.** Point it at any documentation site, get clean Markdown files ready for your AI.

## What it does

- **🎯 Zero config**: Just provide a URL, get perfect Markdown
- **🤖 AI-optimized**: Clean, structured output perfect for LLMs
- **📁 Smart organization**: Automatically organizes content by URL structure
- **⚡ Intelligent crawling**: Finds sitemaps, filters doc pages, respects rate limits
- **🔄 Incremental updates**: Only re-downloads changed pages

## Quick Start

### 1. Install
```bash
pip install aimdoc  # (coming soon)
# For now:
git clone https://github.com/your-org/aimdoc
pip install -r requirements.txt
```

### 2. Create a simple config
```bash
echo '{"name": "react-docs", "url": "https://react.dev"}' > config.json
```

### 3. Extract documentation
```bash
scrapy crawl aimdoc -a manifest=config.json
```

### 4. Use with your AI
Your documentation is now in `build/` as clean Markdown files, ready to feed to ChatGPT, Claude, or any LLM!

## Real-world examples

```bash
# Get React docs for your AI
echo '{"name": "react", "url": "https://react.dev"}' > react.json
scrapy crawl aimdoc -a manifest=react.json

# Get Vue docs  
echo '{"name": "vue", "url": "https://vuejs.org"}' > vue.json
scrapy crawl aimdoc -a manifest=vue.json

# Get any framework docs
echo '{"name": "nextjs", "url": "https://nextjs.org"}' > next.json  
scrapy crawl aimdoc -a manifest=next.json
```

## Manifest Configuration

Create a minimal JSON manifest file:

```json
{
  "name": "project-docs",
  "url": "https://docs.example.com"
}
```

That's it! DocPack automatically:
- **Discovers sitemaps** from `robots.txt` and common locations
- **Filters documentation URLs** (paths containing `/docs/`, `/api/`, `/guide/`, etc.)
- **Extracts content** using universal selectors that work on 95% of sites
- **Organizes files** based on URL structure (`/docs/api/reference/` → `api/reference.md`)
- **Respects rate limits** using Scrapy's intelligent auto-throttling

### Configuration Options

- **name**: Project name (used in output filenames) - **Required**
- **url**: Base URL of the documentation site - **Required**

### Advanced Options (Optional)

For sites that need custom configuration, you can add:

```json
{
  "name": "project-docs", 
  "url": "https://docs.example.com",
  "output": {"mode": "single"},
  "selectors": {
    "content": ".custom-content-selector"
  }
}
```

- **output.mode**: "bundle" (default, separate files) or "single" (one file)
- **selectors.title**: Custom title selector (default: universal selectors)
- **selectors.content**: Custom content selector (default: universal selectors)

## Output Structure

### Bundle Mode (default)

```
build/
├── README.md              # Overview with table of contents
├── chapters/              # Individual chapter files
│   ├── 01-introduction.md
│   ├── 02-getting-started.md
│   └── ...
├── SOURCES.json           # Source metadata and freshness info
└── CHANGELOG.md           # Change tracking between builds
```

### Single File Mode

```
build/
├── project-docs.md        # All content in single file
├── SOURCES.json           # Source metadata
└── CHANGELOG.md           # Change tracking
```

## Output Features

### Front Matter

Each output includes YAML front matter:

```yaml
---
title: "DocPack: project-docs"
built_at: 2025-08-31T12:00:00.000Z
sources: 25
version: "2025.08.31"
scope: ["https://docs.example.com/**"]
---
```

### Source Attribution

Each chapter includes source attribution:

```markdown
<!-- source: https://docs.example.com/guide | fetched: 2025-08-31T12:00:00Z -->
```

### Change Tracking

CHANGELOG.md tracks changes between builds:

```markdown
## 2025.08.31 - 2025-08-31 12:00:00 UTC

### Summary
- **Total pages:** 25
- **Changes:** 3
  - Added: 1
  - Modified: 2
  - Removed: 0

### Added Pages
- [New Feature Guide](https://docs.example.com/new-feature)

### Modified Pages  
- [Getting Started](https://docs.example.com/start) - content, title
- [API Reference](https://docs.example.com/api) - content
```

## Examples

See the `examples/` directory for sample manifest files:

- `examples/scrapy-docs.json` - Scraping Scrapy documentation
- `examples/single-file.json` - Single file output example

## Architecture

- **Spider**: `DocpackSpider` handles URL discovery and page crawling
- **Pipelines**:
  - `CleanHtmlPipeline`: Removes navigation and noise
  - `HtmlToMarkdownPipeline`: Converts HTML to markdown
  - `AssemblePipeline`: Generates final output files
  - `DiffPipeline`: Tracks changes and generates changelog

## Requirements

- Python 3.8+
- Scrapy 2.8+
- BeautifulSoup4 4.11+
- markdownify 0.11+

## License

MIT License