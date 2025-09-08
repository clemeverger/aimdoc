#!/bin/bash

# Setup script for Aimdoc - Pure Python CLI Tool

echo "🚀 Setting up Aimdoc CLI..."

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3.8+ is required but not installed."
    echo "Please install Python 3.8 or later and try again."
    exit 1
fi

# Check Python version
python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if [ "$(printf '%s\n' "3.8" "$python_version" | sort -V | head -n1)" != "3.8" ]; then
    echo "❌ Python 3.8+ is required. Current version: $python_version"
    exit 1
fi

# Check if pip is available
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is required but not installed."
    echo "Please install pip and try again."
    exit 1
fi

echo "📦 Installing Python dependencies..."
pip3 install -r requirements.txt

echo "🔧 Installing Aimdoc in development mode..."
pip3 install -e .

echo "✅ Setup complete!"
echo ""
echo "🎯 Quick Start:"
echo ""
echo "   # Interactive mode - just follow the prompts!"
echo "   aimdoc scrape"
echo ""
echo "   # Or specify everything upfront:"
echo "   aimdoc scrape https://docs.example.com --name \"Example Docs\" --output-dir ./my-docs"
echo ""
echo "📚 Commands:"
echo "   aimdoc --help      # Show all available commands"
echo "   aimdoc version     # Show version information"
echo "   aimdoc scrape      # Start interactive scraping"
echo ""
echo "💡 Aimdoc is now a pure Python CLI tool - no server required!"