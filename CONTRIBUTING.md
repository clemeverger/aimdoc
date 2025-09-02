# Contributing to aimdoc

Thanks for your interest in contributing to aimdoc! 🎯

## Quick Start

1. **Fork and clone**
```bash
git clone https://github.com/your-username/aimdoc.git
cd aimdoc
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Test your changes**
```bash
scrapy crawl aimdoc -a manifest=test-ai-sdk-simple.json
```

## What we need help with

### 🐛 Bug fixes
- Sites that don't extract properly
- Encoding issues
- Performance problems

### ✨ Features  
- Better content detection
- More output formats
- CLI wrapper around Scrapy

### 📚 Documentation
- More example configs
- Better error messages
- Usage guides

### 🧪 Testing
- Test against more documentation sites
- Edge case handling
- Performance testing

## Guidelines

### Code style
- Follow existing patterns
- Keep it simple and readable  
- Universal selectors over site-specific code

### Commit messages
- Use conventional commits: `feat:`, `fix:`, `docs:`
- Be descriptive but concise

### Pull requests
- One feature/fix per PR
- Test against real documentation sites
- Update examples if needed

## Questions?

Open an issue or discussion - we're happy to help! 🚀