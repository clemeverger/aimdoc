#!/bin/bash

# Setup script for Aimdoc API + CLI

echo "🚀 Setting up Aimdoc API and CLI..."

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi

# Check if pnpm is available
if ! command -v pnpm &> /dev/null; then
    echo "❌ pnpm is required but not installed."
    echo "Install it with: npm install -g pnpm"
    exit 1
fi

echo "📦 Installing Python dependencies..."
pip3 install -r requirements.txt

echo "🏗️  Building CLI..."
cd cli
pnpm install
pnpm run build
cd ..

echo "✅ Setup complete!"
echo ""
echo "🎯 Quick Start:"
echo "1. Start the API server:"
echo "   python3 start_api.py"
echo ""
echo "2. In another terminal, use the CLI:"
echo "   cd cli && pnpm run dev scrape https://react.dev"
echo ""
echo "   Or install globally:"
echo "   cd cli && pnpm link --global"
echo "   aimdoc scrape https://react.dev"
echo ""
echo "📚 Documentation:"
echo "- API docs: http://localhost:8000/docs"
echo "- CLI help: aimdoc --help"