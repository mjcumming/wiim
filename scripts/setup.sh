#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."

echo "🚀 Setting up WiiM development environment..."

# Install Python dependencies
echo "📦 Installing Python packages..."
pip install --upgrade pip setuptools wheel
pip install --constraint=.github/workflows/constraints.txt -r requirements_test.txt

# Hook installation is optional and must not replace an existing hook setup.
echo "ℹ️  Optional staged-file checks: pre-commit install"

# Create Home Assistant configuration directory
echo "📁 Creating Home Assistant config directory..."
mkdir -p config/custom_components

# Link the integration
if [ -e config/custom_components/wiim ] || [ -L config/custom_components/wiim ]; then
    echo "ℹ️  Existing WiiM config entry preserved."
else
    echo "🔗 Linking WiiM integration..."
    ln -s "$(pwd)/custom_components/wiim" config/custom_components/wiim
fi

# Create a basic configuration.yaml
if [ -e config/configuration.yaml ] || [ -L config/configuration.yaml ]; then
    echo "ℹ️  Existing Home Assistant configuration preserved."
else
    echo "📝 Creating Home Assistant configuration..."
    cat > config/configuration.yaml << EOYAML
# Basic Home Assistant configuration for development
default_config:

# Enable debug logging for the integration
logger:
  default: info
  logs:
    custom_components.wiim: debug

# Add speakers through the Home Assistant integrations UI.
EOYAML
fi

echo "✅ Development environment ready!"
echo ""
echo "To start Home Assistant:"
echo "  hass -c config"
echo ""
echo "To run tests:"
echo "  pytest"
echo ""
