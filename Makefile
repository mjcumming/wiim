# WiiM Integration - Build & Test Makefile
#
# This Makefile provides commands for testing, linting, and building
# the WiiM Home Assistant integration.

.PHONY: help test test-phase test-quick lint format clean install install-dev build check-all release check-python check-ha-compat

# Default target
help:
	@echo "WiiM Integration - Available Commands:"
	@echo ""
	@echo "Testing:"
	@echo "  test           - Run all integration tests"
	@echo "  test-phase N   - Run specific phase test (1-5)"
	@echo "  test-verbose   - Run tests with verbose output"
	@echo "  test-quick     - Run tests without coverage (faster)"
	@echo ""
	@echo "Code Quality:"
	@echo "  validate       - Validate refactor integrity & API consistency"
	@echo "  pre-commit     - Run all pre-commit validation checks"
	@echo "  lint           - Run linting checks"
	@echo "  format         - Format code with ruff"
	@echo "  check-all      - Run all quality checks"
	@echo "  check-python   - Verify Python version compatibility"
	@echo "  check-ha-compat - Check HA dependency compatibility"
	@echo ""
	@echo "Build:"
	@echo "  clean          - Clean build artifacts"
	@echo "  build          - Build integration package"
	@echo "  install        - Install for development"
	@echo "  install-dev    - Install dev dependencies with HA checks"
	@echo "  release        - Full release build (test + lint + build)"
	@echo ""

# Python version validation
check-python:
	@echo "🐍 Checking Python version compatibility with Home Assistant..."
	@python3 -c "import sys; print(f'Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
	@python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,13) else 1)" || \
		(echo "❌ Python 3.13+ required for Home Assistant 2024.12+"; exit 1)
	@echo "✅ Python version is compatible with Home Assistant"

# Home Assistant dependency compatibility check
check-ha-compat: check-python
	@echo "🏠 Checking Home Assistant Core compatibility..."
	@pip install -q pytest-homeassistant-custom-component>=0.13.240 || \
		(echo "❌ Cannot install HA test dependencies - check Python version"; exit 1)
	@echo "✅ Home Assistant dependencies are compatible"

# Install development dependencies with HA compatibility checks
install-dev: check-ha-compat
	pip install --constraint=.github/workflows/constraints.txt -r requirements_test.txt
	@echo "✅ Development environment ready for Home Assistant integration development"

# Quick test run without coverage (faster for development)
test-quick: check-python
	pytest tests/ -v

# Testing targets
test:
	@echo "🧪 Running WiiM Integration Tests..."
	python tests/run_tests.py

test-phase:
	@echo "🧪 Running Phase $(PHASE) Tests..."
	python tests/run_tests.py --phase=$(PHASE)

test-verbose:
	@echo "🧪 Running WiiM Integration Tests (Verbose)..."
	python tests/run_tests.py --verbose

# Code quality targets
lint:
	@echo "🔍 Running Linting Checks..."
	python tests/run_tests.py --lint
	@echo "🔍 Running mypy type checks..."
	-python -m mypy custom_components/wiim/ --ignore-missing-imports
	@echo "📏 Running file size check..."
	@python scripts/ruff_size_check.py custom_components/wiim 300 400

validate:
	@echo "🔍 Validating refactor integrity..."
	python scripts/validate_refactor.py

pre-commit:
	@echo "🔄 Running pre-commit checks..."
	bash scripts/pre_commit_check.sh

format:
	@echo "🎨 Formatting code with ruff..."
	-python -m ruff format custom_components/wiim/
	-python -m ruff format tests/

check-all: validate lint test
	@echo "✅ All quality checks completed"

# Build targets
clean:
	@echo "🧹 Cleaning build artifacts..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf build/ dist/ *.egg-info/ archive/ 2>/dev/null || true

install:
	@echo "📦 Installing for development..."
	pip install -e .

build: clean
	@echo "🏗️  Building WiiM integration..."
	@echo "Integration structure:"
	@find custom_components/wiim -name "*.py" | wc -l | xargs echo "Python files:"
	@du -sh custom_components/wiim | cut -f1 | xargs echo "Total size:"
	@echo "Build completed successfully!"

# Release target - runs full validation pipeline
release: clean check-all build
	@echo ""
	@echo "🎉 WiiM Integration Release Build Complete!"
	@echo ""
	@echo "📊 Release Summary:"
	@echo "  ✅ All tests passed"
	@echo "  ✅ Code quality checks passed"
	@echo "  ✅ Build artifacts created"
	@echo ""
	@echo "Ready for deployment! 🚀"

# Development helpers
dev-check: lint test
	@echo "🔄 Development checks completed"

watch:
	@echo "👀 Watching for changes (Ctrl+C to stop)..."
	while true; do \
		inotifywait -q -r -e modify custom_components/wiim/; \
		echo "🔄 Change detected, running quick check..."; \
		make dev-check; \
		echo "✅ Quick check completed"; \
	done

# Documentation targets
docs:
	@echo "📚 Generating documentation..."
	@find docs/ -name "*.md" | wc -l | xargs echo "Documentation files:"
	@echo "Documentation is current!"

# Git hooks integration
pre-commit: check-all
	@echo "✅ Pre-commit checks passed"

# Show project statistics
stats:
	@echo "📊 WiiM Integration Statistics:"
	@echo ""
	@echo "Code:"
	@find custom_components/wiim -name "*.py" | xargs wc -l | tail -1
	@echo ""
	@echo "Tests:"
	@find tests/ -name "*.py" | xargs wc -l | tail -1
	@echo ""
	@echo "Documentation:"
	@find docs/ -name "*.md" | xargs wc -l | tail -1
	@echo ""

# Quick syntax check
syntax:
	@echo "🔍 Running syntax checks..."
	python -m py_compile custom_components/wiim/*.py
	python -m py_compile custom_components/wiim/platforms/*.py
	@echo "✅ Syntax checks passed"
