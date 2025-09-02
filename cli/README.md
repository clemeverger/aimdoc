# Aimdoc CLI

Command line interface for the Aimdoc API - AI-friendly documentation scraper.

## Installation

```bash
# Navigate to CLI directory
cd cli

# Install dependencies
pnpm install

# Build the CLI
pnpm run build

# Link globally (optional)
pnpm link --global
```

## Usage

### Basic Commands

#### Scrape Documentation

```bash
# Interactive mode
aimdoc scrape

# Direct URL
aimdoc scrape https://react.dev

# With options
aimdoc scrape https://docs.python.org \
  --name python-docs \
  --mode single \
  --wait

# Custom selectors
aimdoc scrape https://example.com \
  --title-selector "h1, .page-title" \
  --content-selector "article, .content"
```

#### Check Job Status

```bash
# Basic status
aimdoc status abc123def

# Verbose output
aimdoc status abc123def --verbose
```

#### List Jobs

```bash
# Recent jobs (default: 10)
aimdoc list

# Show all jobs
aimdoc list --all

# Limit results
aimdoc list --limit 5
```

#### Download Results

```bash
# Download all files
aimdoc download abc123def

# Download to specific directory
aimdoc download abc123def --output ./downloads

# Download specific file
aimdoc download abc123def --file README.md

# Force overwrite existing files
aimdoc download abc123def --overwrite
```

#### View Results

```bash
# Show file list and metadata
aimdoc results abc123def
```

#### Delete Jobs

```bash
# Delete with confirmation
aimdoc delete abc123def

# Force delete without confirmation
aimdoc delete abc123def --force
```

### Configuration

#### Interactive Configuration

```bash
aimdoc config
```

#### Show Current Config

```bash
aimdoc config --show
```

#### Set Specific Options

```bash
# Set API URL
aimdoc config --api-url http://localhost:8000

# Set timeout
aimdoc config --timeout 60000

# Reset to defaults
aimdoc config --reset
```

## Configuration File

The CLI stores configuration in `~/.aimdoc/config.json`:

```json
{
  "api_url": "http://localhost:8000",
  "timeout": 30000
}
```

## Options Reference

### Scrape Command

- `--name, -n <name>`: Project name for the documentation
- `--mode, -m <mode>`: Output mode (`bundle` or `single`)
- `--title-selector <selector>`: Custom CSS selector for titles
- `--content-selector <selector>`: Custom CSS selector for content
- `--wait, -w`: Wait for job completion
- `--no-progress`: Disable progress monitoring

### Global Options

- `--help, -h`: Show help
- `--version`: Show version

## Environment Variables

- `DEBUG=1`: Enable debug output for troubleshooting

## Examples

### Basic Documentation Scraping

```bash
# Scrape React documentation
aimdoc scrape https://react.dev --name react --wait

# Check the status
aimdoc status abc123def

# Download results
aimdoc download abc123def --output ./react-docs
```

### Batch Operations

```bash
# List recent jobs
aimdoc list

# Download multiple completed jobs
for job in $(aimdoc list | grep COMPLETED | cut -d' ' -f1); do
  aimdoc download $job --output ./docs/$job
done
```

### Custom Configuration

```bash
# Set up custom API endpoint
aimdoc config --api-url https://my-api.example.com

# Increase timeout for large sites
aimdoc config --timeout 120000
```

## Troubleshooting

### API Connection Issues

```bash
# Check API health
curl http://localhost:8000/health

# Test with debug output
DEBUG=1 aimdoc list
```

### Common Issues

1. **API not available**: Make sure the FastAPI server is running
2. **Permission denied**: Check file permissions in output directory
3. **Timeout errors**: Increase timeout in config or use `--timeout`
4. **Large sites**: Use `--no-progress` for better performance

## Development

```bash
# Install dependencies
pnpm install

# Development mode (TypeScript)
pnpm run dev scrape --help

# Build
pnpm run build

# Run tests
pnpm test
```
