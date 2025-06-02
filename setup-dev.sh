#!/bin/bash
# WiiM Integration Development Environment Setup Script
# Run this once after cloning the repository

set -e  # Exit on any error

echo "🔧 Setting up WiiM development environment..."

# Check Python version
echo "🐍 Checking Python version..."
python3 --version
if ! python3 -c "import sys; exit(0 if sys.version_info >= (3,12) else 1)"; then
    echo "❌ Python 3.12+ required"
    exit 1
fi
echo "✅ Python version OK"

# Install development dependencies
echo "📦 Installing development dependencies..."
if ! command -v pip &> /dev/null; then
    echo "❌ pip not found"
    exit 1
fi

pip install -r requirements_test.txt

# Install pre-commit hooks
echo "🪝 Installing pre-commit hooks..."
if ! command -v pre-commit &> /dev/null; then
    echo "📦 Installing pre-commit..."
    pip install pre-commit
fi

pre-commit install
echo "✅ Pre-commit hooks installed"

# Test the setup
echo "🧪 Testing setup..."
make check-python
echo "✅ Python version check passed"

echo "🎉 Development environment setup complete!"
echo ""
echo "📚 Next steps:"
echo "  • Run 'make help' to see available commands"
echo "  • Run 'make check-all' before committing"
echo "  • Read DEVELOPMENT.md for detailed workflows"
echo ""
echo "⚡ Quick commands:"
echo "  make dev-check     # Fast development checks"
echo "  make check-all     # Full CI simulation"
echo "  make test-quick    # Quick tests"
