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
- **🚀 API & CLI**: RESTful API with beautiful command-line interface

## Quick Start

### Method 1: Using the CLI (Recommended)

```bash
# 1. Setup (one-time)
./setup.sh

# 2. Start the API server
python3 start_api.py

# 3. In another terminal, use the CLI
cd cli
pnpm run dev scrape https://react.dev --wait

# Or install globally and use anywhere
pnpm link --global
aimdoc scrape https://react.dev
```

### Method 2: Direct API Usage

```bash
# 1. Start the API
python3 start_api.py

# 2. Create a scrape job
curl -X POST "http://localhost:8000/api/v1/scrape" \
  -H "Content-Type: application/json" \
  -d '{"name": "react-docs", "url": "https://react.dev"}'

# 3. Check status and download results
curl "http://localhost:8000/api/v1/jobs/{job_id}"
```

### Method 3: Traditional Scrapy (Legacy)

```bash
# Create config and run scrapy directly
echo '{"name": "react-docs", "url": "https://react.dev"}' > config.json
scrapy crawl aimdoc -a manifest=config.json
```

## Architecture

Aimdoc now offers three ways to use it:

### 🖥️ **CLI Interface**

Beautiful command-line interface with progress bars, colored output, and interactive prompts.

```bash
aimdoc scrape https://docs.python.org --name python --wait
aimdoc list
aimdoc download abc123def
```

### 🌐 **REST API**

Full-featured REST API for integration into other tools and services.

- **Swagger docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health check**: http://localhost:8000/health

### ⚙️ **Direct Scrapy**

Traditional scrapy interface for advanced users and automation.

## API Endpoints

| Method   | Endpoint                                     | Description                   |
| -------- | -------------------------------------------- | ----------------------------- |
| `POST`   | `/api/v1/scrape`                             | Create and start a scrape job |
| `GET`    | `/api/v1/jobs`                               | List all jobs                 |
| `GET`    | `/api/v1/jobs/{job_id}`                      | Get job status                |
| `GET`    | `/api/v1/jobs/{job_id}/results`              | Get job results               |
| `GET`    | `/api/v1/jobs/{job_id}/download/{file_path}` | Download specific file        |
| `DELETE` | `/api/v1/jobs/{job_id}`                      | Delete job                    |
| `POST`   | `/api/v1/jobs/{job_id}/cancel`               | Cancel running job            |

## Real-world examples

### CLI Examples

```bash
# Interactive scraping
aimdoc scrape

# Scrape with options
aimdoc scrape https://react.dev --name react --mode bundle --wait

# List and manage jobs
aimdoc list
aimdoc status abc123def --verbose
aimdoc download abc123def --output ./docs

# Configuration
aimdoc config --api-url http://localhost:8000
```

### API Examples

```bash
# Start a job
curl -X POST "http://localhost:8000/api/v1/scrape" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "vue-docs",
    "url": "https://vuejs.org",
    "output_mode": "single"
  }'

# Check all jobs
curl "http://localhost:8000/api/v1/jobs"

# Download results
curl "http://localhost:8000/api/v1/jobs/{job_id}/download/README.md" \
  --output vue-readme.md
```

### Legacy Scrapy Examples

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

That's it! Aimdoc automatically:

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
  "output": { "mode": "single" },
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
title: 'DocPack: project-docs'
built_at: 2025-08-31T12:00:00.000Z
sources: 25
version: '2025.08.31'
scope: ['https://docs.example.com/**']
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

Aimdoc consists of three main components:

### API Server

- **FastAPI Backend**: Handles job management and provides RESTful endpoints
- **Job Service**: Manages scraping jobs and their lifecycle

### CLI Tool

- **TypeScript/Node.js**: Modern CLI with interactive prompts and progress tracking
- **Commands**: scrape, list, status, download, results, delete, config

### Scraping Engine

- **Spider**: `AimdocSpider` handles URL discovery and page crawling
- **Pipelines**:
  - `CleanHtmlPipeline`: Removes navigation and noise
  - `HtmlToMarkdownPipeline`: Converts HTML to markdown
  - `AssemblePipeline`: Generates final output files
  - `DiffPipeline`: Tracks changes and generates changelog

## Requirements

### Backend

- Python 3.8+
- Scrapy 2.8+
- FastAPI 0.104+
- Uvicorn 0.24+
- BeautifulSoup4 4.11+
- markdownify 0.11+

### CLI

- Node.js 16+
- npm or pnpm

## Deployment

Aimdoc can be deployed to cloud platforms like Render:

1. Push your code to a Git repository
2. Connect your repository to Render
3. Deploy as a Web Service using the provided `render.yaml` configuration

## License

MIT License
