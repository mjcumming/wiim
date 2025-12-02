#!/bin/bash
# Run all CI checks locally before pushing
# Usage: ./scripts/check-before-push.sh

set -e

echo "🔍 Running pre-push checks..."
echo ""

echo "1️⃣  Ruff lint check..."
ruff check custom_components/wiim --line-length 120
echo "   ✅ Ruff passed"
echo ""

echo "2️⃣  Flake8 check..."
flake8 custom_components/wiim --max-line-length=120 --extend-ignore=E203,W503
echo "   ✅ Flake8 passed"
echo ""

echo "3️⃣  MyPy type check..."
mypy --strict custom_components/wiim
echo "   ✅ MyPy passed"
echo ""

echo "4️⃣  Running tests with coverage..."
python -m pytest tests/unit/ -q --cov=custom_components/wiim --cov-fail-under=70
echo "   ✅ Tests passed with coverage ≥70%"
echo ""

echo "🎉 All checks passed! Safe to push."

