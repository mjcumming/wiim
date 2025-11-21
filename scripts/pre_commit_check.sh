#!/bin/bash
# Pre-commit validation script to catch refactor issues

set -e  # Exit on any error

echo "🔍 Running pre-commit refactor validations..."

# 1. Quick syntax check
echo "📋 Syntax check..."
python -m py_compile custom_components/wiim/*.py

# 2. Quick pattern check
echo "🚀 Pattern check..."
python scripts/quick_check.py custom_components/wiim/

# 3. Full validation
echo "🔍 Full validation..."
python scripts/validate_refactor.py

# 4. Basic import test
echo "📦 Import test..."
python -c "
import sys
sys.path.insert(0, '.')
from pywiim import WiiMClient
from custom_components.wiim.coordinator import WiiMCoordinator
print('✅ Core imports successful')
"

echo "✅ All pre-commit checks passed!"
