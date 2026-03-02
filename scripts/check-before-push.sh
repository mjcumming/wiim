#!/bin/bash
# Run EXACT same checks as CI before pushing
# Usage: ./scripts/check-before-push.sh
#
# This matches .github/workflows/tests.yaml exactly
# PLUS checks patch coverage to catch Codecov failures before push

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
pytest tests/ --cov=custom_components/wiim --cov-report=term-missing --cov-report=xml:build/coverage.xml -q
echo "   ✅ Tests passed"
echo ""

# Check patch coverage (same as Codecov)
# This catches the "codecov/patch" failure before pushing
echo "5️⃣  Patch coverage check (Codecov simulation)..."

# Keep local gate aligned with Codecov patch target.
# Override via env var when Codecov target changes:
#   CODECOV_PATCH_TARGET=81.0 ./scripts/check-before-push.sh
PATCH_TARGET="${CODECOV_PATCH_TARGET:-75}"

# Get the compare branch (origin/main or HEAD~1 if main)
COMPARE_BRANCH="origin/main"
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" = "main" ]; then
    # On main, compare with previous commit
    COMPARE_BRANCH="HEAD~1"
fi

# Check if there are changes to Python files
CHANGED_FILES=$(git diff --name-only "$COMPARE_BRANCH" -- 'custom_components/wiim/*.py' 2>/dev/null || echo "")

if [ -n "$CHANGED_FILES" ]; then
    # Run diff-cover with the configured Codecov-aligned threshold.
    if diff-cover build/coverage.xml --compare-branch="$COMPARE_BRANCH" --fail-under="$PATCH_TARGET" --quiet 2>/dev/null; then
        PATCH_COVERAGE=$(diff-cover build/coverage.xml --compare-branch="$COMPARE_BRANCH" 2>/dev/null | grep -oP '[\d.]+(?=%)' | head -1 || echo "100")
        echo "   ✅ Patch coverage: ${PATCH_COVERAGE}% (target: ${PATCH_TARGET}%)"
    else
        echo ""
        echo "   ❌ PATCH COVERAGE FAILED!"
        echo ""
        echo "   Codecov requires ${PATCH_TARGET}% coverage on new/changed lines."
        echo "   Your changes don't have enough test coverage."
        echo ""
        echo "   Run this to see uncovered lines:"
        echo "   diff-cover build/coverage.xml --compare-branch=$COMPARE_BRANCH"
        echo ""
        exit 1
    fi
else
    echo "   ⏭️  No Python changes to check (skipped)"
fi
echo ""

echo "════════════════════════════════════════════"
echo "🎉 ALL CI CHECKS PASSED - Safe to push!"
echo "════════════════════════════════════════════"
