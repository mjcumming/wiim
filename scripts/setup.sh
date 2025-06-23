#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."

echo "🚀 Setting up WiiM development environment..."

# Install Python dependencies
echo "📦 Installing Python packages..."
pip install --upgrade pip setuptools wheel
pip install -r requirements_test.txt

# Install pre-commit hooks if available
if [ -f ".pre-commit-config.yaml" ]; then
    echo "🔧 Installing pre-commit hooks..."
    pre-commit install
fi

# Create Home Assistant configuration directory
echo "📁 Creating Home Assistant config directory..."
mkdir -p config/custom_components

# Link the integration
echo "🔗 Linking WiiM integration..."
rm -rf config/custom_components/wiim
ln -sf "$(pwd)/custom_components/wiim" config/custom_components/

# Create a basic configuration.yaml
echo "📝 Creating Home Assistant configuration..."
cat > config/configuration.yaml << EOYAML
# Basic Home Assistant configuration for development
default_config:

# Enable debug logging for the integration
logger:
  default: info
  logs:
    custom_components.wiim: debug

# If you want to add test devices, uncomment and configure:
# wiim:
#   - host: 192.168.1.100
#     name: "Living Room WiiM"
EOYAML

echo "✅ Development environment ready!"
echo ""
echo "To start Home Assistant:"
echo "  hass -c config"
echo ""
echo "To run tests:"
echo "  pytest"
echo ""
