# WiiM Home Assistant Integration - Development Makefile
# Run these commands before committing to catch issues early

.PHONY: help install install-dev test test-quick lint format pre-commit check-all clean

# Default target
help:
	@echo "Available targets:"
	@echo "  install     - Install runtime dependencies only"
	@echo "  install-dev - Install all development dependencies"
	@echo "  test        - Run full test suite with coverage"
	@echo "  test-quick  - Run tests without coverage (faster)"
	@echo "  lint        - Run all linting checks"
	@echo "  format      - Auto-format code"
	@echo "  pre-commit  - Run pre-commit hooks on all files"
	@echo "  check-all   - Run all checks (same as CI pipeline)"
	@echo "  clean       - Clean up temporary files"
	@echo ""
	@echo "Recommended workflow:"
	@echo "  make install-dev  # First time setup"
	@echo "  make check-all    # Before each commit"

# Install runtime dependencies only
install:
	pip install --constraint=.github/workflows/constraints.txt pip
	pip install -r requirements.txt

# Install all development dependencies (equivalent to CI setup)
install-dev:
	pip install --constraint=.github/workflows/constraints.txt pip
	pip install --constraint=.github/workflows/constraints.txt pre-commit
	pip install --constraint=.github/workflows/constraints.txt -r requirements_test.txt
	pre-commit install

# Run full test suite with coverage (same as CI)
test:
	@echo "🧪 Running tests with coverage..."
	pytest \
		--timeout=9 \
		--durations=10 \
		--cov=custom_components.wiim \
		--cov-report=xml \
		--cov-report=term-missing \
		--cov-fail-under=10 \
		-v \
		tests

# Run tests quickly without coverage
test-quick:
	@echo "🚀 Running quick tests..."
	pytest -v tests

# Run all linting checks
lint:
	@echo "🔍 Running linting checks..."
	black --check custom_components tests
	flake8 custom_components tests
	isort --check-only custom_components tests

# Auto-format code
format:
	@echo "✨ Formatting code..."
	black custom_components tests
	isort custom_components tests
	reorder-python-imports --py312-plus custom_components/**/*.py tests/**/*.py

# Run pre-commit hooks on all files (same as CI)
pre-commit:
	@echo "🔧 Running pre-commit hooks..."
	pre-commit run --all-files --show-diff-on-failure --color=always

# Check Python version compatibility
check-python:
	@echo "🐍 Checking Python version compatibility..."
	@python -c "import sys; print(f'Python version: {sys.version}'); exit(0 if sys.version_info >= (3,12) else 1)" || \
		(echo "❌ Python 3.12+ required"; exit 1)
	@echo "✅ Python version OK"

# Validate Home Assistant integration
hassfest:
	@echo "🏠 Running Home Assistant validation..."
	@if command -v hass >/dev/null 2>&1; then \
		echo "Using local hass command..."; \
		hass --script hassfest --integration-path ./custom_components/wiim; \
	else \
		echo "⚠️  hass command not found - skipping hassfest (will run in CI)"; \
	fi

# Run all checks (equivalent to full CI pipeline)
check-all: check-python pre-commit test hassfest
	@echo ""
	@echo "🎉 All checks passed! Ready to commit."

# Clean up temporary files
clean:
	@echo "🧹 Cleaning up..."
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf coverage.xml
	rm -rf custom_components/**/__pycache__/
	rm -rf tests/**/__pycache__/
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} +

# Check if we're ready to commit (quick version)
ready:
	@echo "🚦 Quick readiness check..."
	@make check-python
	@make lint
	@make test-quick
	@echo "✅ Ready for commit (run 'make check-all' for full CI simulation)"

# Development workflow - run this after making changes
dev-check: format ready
	@echo "🚀 Development check complete!"
