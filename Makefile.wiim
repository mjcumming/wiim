# WiiM Home Assistant Integration - Development Makefile
# Run these commands before committing to catch issues early

.PHONY: help install install-dev test test-quick lint format pre-commit check-all clean check-python check-ha-compatibility

# Default target
help:
	@echo "Available targets:"
	@echo "  install        - Install runtime dependencies only"
	@echo "  install-dev    - Install all development dependencies"
	@echo "  test           - Run full test suite with coverage"
	@echo "  test-quick     - Run tests without coverage (faster)"
	@echo "  lint           - Run all linting checks"
	@echo "  format         - Auto-format code"
	@echo "  pre-commit     - Run pre-commit hooks on all files"
	@echo "  check-all      - Run all checks (same as CI pipeline)"
	@echo "  check-python   - Verify Python version matches HA requirements"
	@echo "  check-ha-compat - Check dependency compatibility with HA Core"
	@echo "  clean          - Clean up build artifacts and cache"
	@echo ""
	@echo "Recommended workflow:"
	@echo "  make install-dev  # First time setup"
	@echo "  make check-all    # Before each commit"

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

# Install runtime dependencies
install:
	pip install -r requirements.txt

# Install development dependencies with HA compatibility checks
install-dev: check-ha-compat
	pip install --constraint=.github/workflows/constraints.txt -r requirements_test.txt
	@echo "✅ Development environment ready for Home Assistant integration development"

# Run tests with coverage
test: check-python
	pytest tests/ --cov=custom_components/wiim --cov-report=term-missing --cov-report=xml --cov-fail-under=80

# Quick test run without coverage (faster for development)
test-quick: check-python
	pytest tests/ -v

# Run all linting checks
lint: check-python
	flake8 custom_components/wiim --max-line-length=120 --extend-ignore=E203,W503
	@echo "✅ All linting checks passed"

# Auto-format code
format:
	black custom_components/ tests/ --line-length=120
	@echo "✅ Code formatting applied"

# Run pre-commit hooks
pre-commit: check-python
	pre-commit run --all-files

# Run all checks (matches CI pipeline)
check-all: check-python check-ha-compat lint test
	@echo "🎉 All checks passed! Ready for git commit."

# Development workflow - run this during development
dev-check: check-python lint test-quick
	@echo "🚀 Development checks complete!"

# Clean up build artifacts
clean:
	rm -rf .pytest_cache/
	rm -rf __pycache__/
	rm -rf *.egg-info/
	rm -f .coverage
	rm -f coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	@echo "✅ Cleaned up build artifacts"
