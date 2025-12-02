#!/bin/bash
# Run EXACT same checks as CI before pushing
# Usage: ./scripts/check-before-push.sh
#
# This matches .github/workflows/tests.yaml exactly

set -e
cd "$(dirname "$0")/.."

echo "🔍 Running CI checks locally..."
echo "   (Same checks as .github/workflows/tests.yaml)"
echo ""

echo "1️⃣  Ruff lint..."
ruff check custom_components/wiim --line-length 120
echo "   ✅ Ruff passed"
echo ""

echo "2️⃣  Flake8 lint..."
flake8 custom_components/wiim --max-line-length=120 --extend-ignore=E203,W503
echo "   ✅ Flake8 passed"
echo ""

echo "3️⃣  MyPy strict..."
mypy --strict custom_components/wiim
echo "   ✅ MyPy passed"
echo ""

echo "4️⃣  Pytest with coverage..."
pytest tests/ --cov=custom_components/wiim --cov-report=term-missing -q
echo "   ✅ Tests passed"
echo ""

echo "════════════════════════════════════════════"
echo "🎉 ALL CI CHECKS PASSED - Safe to push!"
echo "════════════════════════════════════════════"
