#!/bin/bash

# HACS Integration Validation Script
# Validates the integration meets HACS requirements before release

set -e

echo "🔍 Validating HACS Integration Compliance..."

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0

# Function to print error
error() {
    echo -e "${RED}❌ ERROR: $1${NC}"
    ERRORS=$((ERRORS + 1))
}

# Function to print success
success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Function to print warning
warning() {
    echo -e "${YELLOW}⚠️  WARNING: $1${NC}"
}

# Check required files
echo "📁 Checking required files..."

if [ ! -f "hacs.json" ]; then
    error "Missing hacs.json file"
else
    success "hacs.json found"
fi

if [ ! -f "custom_components/wiim/manifest.json" ]; then
    error "Missing custom_components/wiim/manifest.json"
else
    success "manifest.json found"
fi

if [ ! -f "README.md" ]; then
    error "Missing README.md"
else
    success "README.md found"
fi

if [ ! -f "CHANGELOG.md" ]; then
    error "Missing CHANGELOG.md"
else
    success "CHANGELOG.md found"
fi

# Check directory structure
echo -e "\n📂 Checking directory structure..."

if [ ! -d "custom_components/wiim" ]; then
    error "Missing custom_components/wiim directory"
else
    success "Integration directory structure correct"
fi

if [ ! -d "docs" ]; then
    error "Missing docs directory"
else
    success "Documentation directory found"
fi

if [ ! -d "examples" ]; then
    error "Missing examples directory"
else
    success "Examples directory found"
fi

# Check integration files
echo -e "\n🔧 Checking integration files..."

REQUIRED_FILES=(
    "__init__.py"
    "manifest.json"
    "config_flow.py"
    "media_player.py"
    "const.py"
    "strings.json"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "custom_components/wiim/$file" ]; then
        error "Missing custom_components/wiim/$file"
    else
        success "Found $file"
    fi
done

# Validate manifest.json
echo -e "\n📋 Validating manifest.json..."

if command -v jq >/dev/null 2>&1; then
    # Check JSON validity
    if jq empty custom_components/wiim/manifest.json 2>/dev/null; then
        success "manifest.json is valid JSON"
    else
        error "manifest.json is not valid JSON"
    fi

    # Check required fields
    DOMAIN=$(jq -r '.domain' custom_components/wiim/manifest.json)
    if [ "$DOMAIN" != "wiim" ]; then
        error "Domain in manifest.json should be 'wiim', found '$DOMAIN'"
    else
        success "Domain is correct"
    fi

    VERSION=$(jq -r '.version' custom_components/wiim/manifest.json)
    if [ "$VERSION" == "null" ] || [ -z "$VERSION" ]; then
        error "Version missing in manifest.json"
    else
        success "Version found: $VERSION"
    fi

    REQUIREMENTS=$(jq -r '.requirements | length' custom_components/wiim/manifest.json)
    if [ "$REQUIREMENTS" -ne 0 ]; then
        warning "Integration has external requirements (should be dependency-free for WiiM)"
    else
        success "No external requirements (dependency-free)"
    fi
else
    warning "jq not installed, skipping JSON validation"
fi

# Validate hacs.json
echo -e "\n📄 Validating hacs.json..."

if command -v jq >/dev/null 2>&1; then
    if jq empty hacs.json 2>/dev/null; then
        success "hacs.json is valid JSON"
    else
        error "hacs.json is not valid JSON"
    fi

    NAME=$(jq -r '.name' hacs.json)
    if [ "$NAME" == "null" ] || [ -z "$NAME" ]; then
        error "Name missing in hacs.json"
    else
        success "Name found: $NAME"
    fi

    ZIP_RELEASE=$(jq -r '.zip_release' hacs.json)
    if [ "$ZIP_RELEASE" != "true" ]; then
        warning "zip_release is not true in hacs.json"
    else
        success "ZIP release enabled"
    fi
fi

# Check documentation quality
echo -e "\n📚 Checking documentation..."

DOC_FILES=(
    "docs/README.md"
    "docs/installation.md"
    "docs/configuration.md"
    "docs/multiroom.md"
    "docs/troubleshooting.md"
)

for doc in "${DOC_FILES[@]}"; do
    if [ ! -f "$doc" ]; then
        error "Missing documentation: $doc"
    else
        success "Found $doc"
    fi
done

# Check examples
echo -e "\n📝 Checking examples..."

EXAMPLE_DIRS=(
    "examples/scripts"
    "examples/templates"
    "examples/lovelace"
)

for dir in "${EXAMPLE_DIRS[@]}"; do
    if [ ! -d "$dir" ]; then
        error "Missing example directory: $dir"
    else
        success "Found $dir"
    fi
done

# Check for common issues
echo -e "\n🔍 Checking for common issues..."

# Check for test files in integration directory
if find custom_components/wiim -name "*test*" -type f | grep -q .; then
    error "Test files found in integration directory (should be in tests/)"
fi

# Check for __pycache__ directories
if find custom_components/wiim -name "__pycache__" -type d | grep -q .; then
    error "__pycache__ directories found (should be in .gitignore)"
fi

# Check for .pyc files
if find custom_components/wiim -name "*.pyc" -type f | grep -q .; then
    error ".pyc files found (should be in .gitignore)"
fi

# Final summary
echo -e "\n📊 Validation Summary"
echo "===================="

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}🎉 All checks passed! Integration is HACS compliant.${NC}"
    echo -e "${GREEN}✅ Ready for release!${NC}"
    exit 0
else
    echo -e "${RED}❌ Found $ERRORS error(s). Please fix before release.${NC}"
    exit 1
fi
