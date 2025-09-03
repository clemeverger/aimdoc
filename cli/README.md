# ⚡ Aimdoc CLI

> **Beautiful Command-Line Interface for Documentation Scraping**  
> Transform any documentation site into AI-ready Markdown with an elegant developer experience

[![npm version](https://img.shields.io/npm/v/aimdoc.svg)](https://www.npmjs.com/package/aimdoc)
[![Node.js](https://img.shields.io/badge/node-16+-green.svg)](https://nodejs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## ✨ **Why Use the CLI?**

The Aimdoc CLI transforms the complex process of documentation scraping into a **beautiful, interactive experience**:

🎯 **Zero Configuration** - Just run `aimdoc scrape` and follow the prompts  
⚡ **Real-Time Progress** - Watch your documentation being scraped with live updates  
🎨 **Beautiful Interface** - Elegant spinners, progress bars, and colored output  
🔍 **Smart Diagnostics** - Detailed error reporting when things go wrong  
📁 **Organized Output** - Clean folder structure with automatic README generation

---

## 🚀 **Installation**

### Global Installation (Recommended)

```bash
# Using npm
npm install -g aimdoc

# Using pnpm
pnpm install -g aimdoc

# Using yarn
yarn global add aimdoc
```

### Local Development

```bash
# Clone and install
git clone https://github.com/clemeverger/aimdoc.git
cd aimdoc/cli
npm install

# Build and link locally
npm run build
npm link

# Or run directly with ts-node
npm run dev scrape --help
```

---

## 🎮 **Commands**

### `aimdoc scrape` - Scrape Documentation

The main command that does all the magic ✨

```bash
# Interactive mode - just follow the prompts!
aimdoc scrape

# Specify URL directly
aimdoc scrape https://nextjs.org/docs

# Full customization
aimdoc scrape https://react.dev \
  --name "React Official Docs" \
  --output-dir ./references/react
```

**Options:**

- `[url]` - Documentation site URL (optional, will prompt if not provided)
- `-n, --name <name>` - Project name (defaults to domain name)
- `-o, --output-dir <dir>` - Output directory (defaults to `./docs`)

**What happens:**

1. 🔍 **URL Validation** - Ensures the URL is valid and accessible
2. 📝 **Interactive Setup** - Prompts for missing information with smart defaults
3. 🚀 **Job Creation** - Starts a scraping job on the API server
4. 📊 **Live Progress** - Shows real-time updates with beautiful progress indicators
5. 📁 **File Organization** - Downloads and organizes files in a clean structure
6. 📋 **Index Generation** - Creates a README.md with navigation links

### `aimdoc jobs` - List All Jobs

See all your scraping jobs at a glance:

```bash
# List all jobs
aimdoc jobs

# Show only recent jobs
aimdoc jobs --limit 10
```

**Output:**

```
📋 Recent Scraping Jobs

✅ nextjs-docs      (a1b2c3d4)  Completed  2 hours ago    247 files
🔄 react-docs       (e5f6g7h8)  Running    Started 5m ago
❌ vue-docs         (i9j0k1l2)  Failed     1 day ago      Connection timeout
⏳ tailwind-docs    (m3n4o5p6)  Pending    Just now
```

### `aimdoc download` - Download Job Results

Download results from a previous job:

```bash
# Download specific job
aimdoc download a1b2c3d4-e5f6-7890-abcd-ef1234567890

# Specify custom output directory
aimdoc download a1b2c3d4-e5f6-7890-abcd-ef1234567890 --output-dir ./my-docs
```

### `aimdoc diagnose` - Debug Failed Jobs

Get detailed diagnostics for failed or problematic scrapes:

```bash
# Basic diagnosis
aimdoc diagnose a1b2c3d4-e5f6-7890-abcd-ef1234567890

# Verbose output with failed pages
aimdoc diagnose a1b2c3d4-e5f6-7890-abcd-ef1234567890 --verbose
```

**Sample Output:**

```
=== Job Diagnosis: a1b2c3d4 ===
Status: ❌ FAILED
Created: 2024-01-15T10:30:00Z
Started: 2024-01-15T10:30:05Z

=== Results Summary ===
📄 Files created: 0
✅ Pages scraped: 0
❌ Pages failed: 5
🔍 Pages discovered: Unknown

=== Detailed Diagnostics ===
❌ Discovery Errors (2):
  1. https://example.com/robots.txt
     Error: DNSLookupError: DNS lookup failed
  2. https://example.com/sitemap.xml
     Error: TimeoutError: Request timed out

💡 Tip: This website appears to have no sitemap or an inaccessible sitemap.
   Consider trying a different website that has a sitemap.xml file.
```

### `aimdoc config` - Configuration Management

Manage CLI configuration and API connection:

```bash
# Show current configuration
aimdoc config show

# Set API server URL
aimdoc config set api-url http://localhost:8000

# Reset to defaults
aimdoc config reset
```

---

## 🎨 **Interactive Experience**

The CLI is designed to be **beautiful and intuitive**. Here's what you'll see:

### 1. **Smart Prompts**

```
? Documentation URL: https://nextjs.org/docs
? Project name: (nextjs) Next.js Official
? Output directory: (./docs) ./references/nextjs
```

### 2. **Elegant Progress Indicators**

```
✓ Job created: a1b2c3d4-e5f6-7890-abcd-ef1234567890
✓ Connected to job
⠋ Discovering sitemap and pages...
✓ Found 247 pages to scrape

Scraping |████████████████████████████████████████| 247/247 pages
✓ Scraping completed!

⠋ Converting to markdown... 247 files created
✓ Converting completed!

⠋ Downloading and organizing files...
✓ Downloaded all 247 files
```

### 3. **Helpful Success Messages**

```
✅ Scraping completed successfully!
✓ Created 247 files from 247 pages
ℹ️  All 247 discovered pages scraped successfully

📁 Documentation organized in: ./references/nextjs
✓ Generated README.md index with 247 files
```

---

## ⚙️ **Configuration**

### Config File Location

The CLI stores configuration in:

- **macOS**: `~/.config/aimdoc/config.yaml`
- **Linux**: `~/.config/aimdoc/config.yaml`
- **Windows**: `%APPDATA%\aimdoc\config.yaml`

### Default Configuration

```yaml
api:
  url: http://localhost:8000
  timeout: 30000

output:
  default_dir: ./docs
  create_readme: true

display:
  show_progress: true
  use_colors: true
  verbose: false
```

### Environment Variables

```bash
# Override API server URL
export AIMDOC_API_URL=http://localhost:8000

# Set default output directory
export AIMDOC_OUTPUT_DIR=./my-docs

# Disable colors (for CI environments)
export NO_COLOR=1
```

---

## 🏗️ **Output Structure**

When you scrape documentation, the CLI creates a clean, organized structure:

```
docs/
└── nextjs/                    # Project name
    ├── README.md              # Auto-generated index
    ├── getting-started/
    │   ├── installation.md
    │   └── quick-start.md
    ├── app-router/
    │   ├── routing.md
    │   ├── pages.md
    │   └── layouts.md
    └── api-reference/
        ├── components.md
        └── functions.md
```

### Auto-Generated README

```markdown
# Documentation Index

Generated on 2024-01-15T14:30:00.000Z

## Structure

- [installation](./getting-started/installation.md)
- [quick-start](./getting-started/quick-start.md)

### app-router

- [routing](./app-router/routing.md)
- [pages](./app-router/pages.md)
- [layouts](./app-router/layouts.md)

### api-reference

- [components](./api-reference/components.md)
- [functions](./api-reference/functions.md)

---

_Generated with [aimdoc](https://github.com/clemeverger/aimdoc)_
```

---

## 🔧 **API Integration**

The CLI communicates with the Aimdoc API server. Make sure it's running:

```bash
# Start the API server (from project root)
python start_api.py

# Check if it's running
curl http://localhost:8000/health
```

### WebSocket Connection

The CLI uses WebSocket for real-time updates during scraping:

- **Connection status** - Shows when connected/disconnected
- **Progress updates** - Live page counts and phase changes
- **Error notifications** - Immediate feedback on failures
- **Completion events** - Automatic download when job finishes

---

## 🎯 **Use Cases**

### For AI Development

```bash
# Get the latest Next.js docs for your AI assistant
aimdoc scrape https://nextjs.org/docs -n "NextJS-Latest" -o ./ai-context

# Scrape multiple frameworks for comparison
aimdoc scrape https://react.dev -n "React" -o ./frameworks
aimdoc scrape https://vuejs.org/guide -n "Vue" -o ./frameworks
aimdoc scrape https://svelte.dev/docs -n "Svelte" -o ./frameworks
```

### For Documentation Teams

```bash
# Monitor competitor documentation
aimdoc scrape https://competitor.com/docs -n "Competitor-Docs"

# Archive documentation versions
aimdoc scrape https://v4.react.dev -n "React-v4" -o ./archives
```

### For Learning & Research

```bash
# Create local documentation library
mkdir ~/dev-docs
aimdoc scrape https://docs.python.org -o ~/dev-docs
aimdoc scrape https://docs.rust-lang.org -o ~/dev-docs
aimdoc scrape https://golang.org/doc -o ~/dev-docs
```

---

## 🐛 **Troubleshooting**

### Common Issues

**❌ Command not found: aimdoc**

```bash
# Make sure it's installed globally
npm list -g aimdoc

# Or install it
npm install -g aimdoc
```

**❌ API connection failed**

```bash
# Check if API server is running
curl http://localhost:8000/health

# Start the API server
cd .. && python start_api.py
```

**❌ Permission denied writing files**

```bash
# Check directory permissions
ls -la ./docs

# Create directory with proper permissions
mkdir -p ./docs && chmod 755 ./docs
```

**❌ WebSocket connection failed**

```bash
# This is usually due to API server not running
# Check the server logs for WebSocket errors
```

### Debug Mode

```bash
# Run with debug logging
DEBUG=aimdoc:* aimdoc scrape https://example.com

# Or use verbose flag
aimdoc scrape https://example.com --verbose
```

### Getting Help

```bash
# Show help for any command
aimdoc --help
aimdoc scrape --help
aimdoc diagnose --help

# Show version
aimdoc --version
```

---

## 🚀 **Performance Tips**

### Faster Scraping

- Use sites with **good sitemaps** (they scrape much faster)
- Choose **smaller documentation sites** for testing
- **Close other applications** to free up system resources

### Better Results

- Prefer **official documentation sites** (they're usually well-structured)
- Avoid sites with **heavy JavaScript** (content might not be accessible)
- Check that the site has a **`/docs/` section** (that's what we target)

### Optimal Workflow

```bash
# 1. Test with a small site first
aimdoc scrape https://small-docs-site.com

# 2. Use diagnose to understand any issues
aimdoc diagnose <job-id> --verbose

# 3. Scale up to larger documentation sites
aimdoc scrape https://large-docs-site.com
```

---

## 🔄 **Updates & Versioning**

### Checking for Updates

```bash
# Check current version
aimdoc --version

# Check for updates (npm)
npm outdated -g aimdoc

# Update to latest version
npm update -g aimdoc
```

### Version Compatibility

- **CLI v1.x** - Compatible with API v1.x
- **Node.js 16+** - Required for modern JavaScript features
- **API Server** - Must be running and accessible

---

## 🤝 **Contributing**

### Development Setup

```bash
# Clone and setup
git clone https://github.com/clemeverger/aimdoc.git
cd aimdoc/cli

# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
```

### Testing

```bash
# Run tests
npm test

# Run tests in watch mode
npm run test:watch

# Test CLI commands
npm run dev scrape --help
```

### Code Style

- **TypeScript** with strict mode enabled
- **Prettier** for code formatting
- **ESLint** for code quality
- **Conventional Commits** for commit messages

---

## 📄 **License**

MIT License - see the [LICENSE](../LICENSE) file for details.

---

<div align="center">

**Built with ❤️ for developers who love beautiful CLIs**

[⭐ Star the project](https://github.com/clemeverger/aimdoc) • [🐛 Report Issues](https://github.com/clemeverger/aimdoc/issues)

</div>
