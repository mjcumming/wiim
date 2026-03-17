#!/bin/bash
# Quick pre-run validation to catch issues before starting Home Assistant
# Usage: ./scripts/pre_run_check.sh

set -e  # Exit on any error

echo "🔍 Running pre-run checks before starting Home Assistant..."

# 1. Syntax check
echo "📋 Checking syntax..."
python3 -m py_compile custom_components/wiim/*.py 2>/dev/null || {
    echo "❌ Syntax errors found!"
    python3 -m py_compile custom_components/wiim/*.py
    exit 1
}

# 2. Ruff linting (quick check)
echo "🔍 Running ruff linting..."
python3 -m ruff check custom_components/wiim/ || {
    echo "❌ Linting errors found! Run 'make format' to auto-fix some issues."
    exit 1
}

# 3. Import test
echo "📦 Testing critical imports..."
python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from custom_components.wiim import DOMAIN
    from custom_components.wiim.coordinator import WiiMCoordinator
    from custom_components.wiim.data import get_coordinator_from_entry, get_all_coordinators
    print('✅ Core imports successful')
except Exception as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)
" || exit 1

echo "✅ All pre-run checks passed! Safe to start Home Assistant."
