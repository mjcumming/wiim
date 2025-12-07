#!/bin/bash
# WiiM Integration Release Script
# Automates the complete release process: linting, testing, versioning, changelog, commit, tag, and push
# A "release" means doing everything - including pushing to GitHub

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_step() {
    echo -e "${BLUE}==>${NC} ${1}"
}

print_success() {
    echo -e "${GREEN}✓${NC} ${1}"
}

print_error() {
    echo -e "${RED}✗${NC} ${1}"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} ${1}"
}

# Get current version from manifest.json
get_current_version() {
    python3 -c "import json; print(json.load(open('custom_components/wiim/manifest.json'))['version'])"
}

# Update version in manifest.json
update_manifest_version() {
    local new_version=$1
    python3 -c "
import json
with open('custom_components/wiim/manifest.json', 'r') as f:
    data = json.load(f)
data['version'] = '${new_version}'
with open('custom_components/wiim/manifest.json', 'w') as f:
    json.dump(data, f, indent=2)
print(f'Updated manifest.json to version ${new_version}')
"
}

# Update CHANGELOG.md with new version header
update_changelog() {
    local new_version=$1
    local date=$(date +%Y-%m-%d)

    # Check if version already exists in changelog
    if grep -q "## \[${new_version}\]" CHANGELOG.md; then
        print_warning "Version ${new_version} already exists in CHANGELOG.md"
        return 0
    fi

    # Add new version header after "# Changelog" line
    sed -i "/^# Changelog/a\\
\\
## [${new_version}] - ${date}\\
\\
### Changed\\
\\
- Release version ${new_version}\\
" CHANGELOG.md

    print_success "Added version ${new_version} to CHANGELOG.md"
}

# Main script
main() {
    print_step "WiiM Integration Release Process"
    echo ""

    # Check if we're in the right directory
    if [[ ! -f "custom_components/wiim/manifest.json" ]]; then
        print_error "Must be run from repository root directory"
        exit 1
    fi

    # Get current version
    CURRENT_VERSION=$(get_current_version)
    print_step "Current version: ${CURRENT_VERSION}"

    # Require version as argument
    if [[ -z "$1" ]]; then
        print_error "Version required. Usage: $0 <version> [--push]"
        print_error "Example: $0 1.0.30"
        print_error "Example: $0 1.0.30 --push  (to also commit, tag, and push)"
        exit 1
    fi

    NEW_VERSION=$1
    shift  # Remove version from arguments

    # Check for --push flag
    PUSH_TO_GIT=false
    while [[ $# -gt 0 ]]; do
        case $1 in
            --push)
                PUSH_TO_GIT=true
                shift
                ;;
            *)
                print_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done

    # Validate version format (semver)
    if ! [[ "$NEW_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        print_error "Invalid version format. Use semantic versioning (e.g., 1.0.30)"
        exit 1
    fi

    print_step "New version: ${NEW_VERSION}"

    echo ""
    print_step "Step 1: Running linting checks..."

    # Run ruff
    print_step "  → Running ruff..."
    if python -m ruff check custom_components/wiim/ --line-length 120; then
        print_success "  Ruff checks passed"
    else
        print_warning "  Ruff checks failed, attempting auto-fix..."
        python -m ruff check custom_components/wiim/ --fix --line-length 120
        python -m ruff format custom_components/wiim/
        # Check again after auto-fix
        if python -m ruff check custom_components/wiim/ --line-length 120; then
            print_success "  Auto-fixed and formatted"
        else
            print_error "  Ruff checks still failed after auto-fix"
            exit 1
        fi
    fi

    # Run flake8
    print_step "  → Running flake8..."
    if flake8 custom_components/wiim --max-line-length=120 --extend-ignore=E203,W503; then
        print_success "  Flake8 checks passed"
    else
        print_error "  Flake8 checks failed"
        exit 1
    fi

    echo ""
    print_step "Step 2: Running tests with coverage..."
    # Ensure build directory exists for coverage XML
    mkdir -p build
    # Run tests with coverage to catch coverage drops before pushing
    # Codecov project coverage threshold is ~77% - fail if below 75% to catch regressions early
    if pytest tests/ --cov=custom_components.wiim --cov-report=term-missing --cov-report=xml:build/coverage.xml --cov-fail-under=75 -q; then
        print_success "All tests passed"

        # Extract coverage percentage from XML report and check against Codecov threshold
        if [[ -f "build/coverage.xml" ]]; then
            COVERAGE_PCT=$(python3 -c "
import xml.etree.ElementTree as ET
try:
    tree = ET.parse('build/coverage.xml')
    root = tree.getroot()
    line_rate = float(root.attrib.get('line-rate', 0))
    coverage_pct = line_rate * 100
    print(f'{coverage_pct:.2f}')
except Exception as e:
    print('0.00')
" 2>/dev/null || echo "0.00")

            # Check if coverage is significantly below Codecov project threshold (~77%)
            # Only warn if coverage is below 72% (5% below threshold) to avoid false alarms
            # Codecov allows small fluctuations, so we don't want to block releases over minor drops
            COVERAGE_CHECK=$(python3 -c "
coverage = float('${COVERAGE_PCT}')
warning_threshold = 72.0  # Warn if below 72% (5% below Codecov threshold)
if coverage < warning_threshold:
    print('WARN')
else:
    print('OK')
" 2>/dev/null || echo "OK")

            if [[ "$COVERAGE_CHECK" == "WARN" ]]; then
                print_warning "Coverage is ${COVERAGE_PCT}% (Codecov project threshold: ~77%)"
                print_warning "This may fail codecov/project check on GitHub. Consider adding tests."
                echo ""
                read -p "Continue with release anyway? (y/N): " -n 1 -r
                echo
                if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                    print_error "Release cancelled by user"
                    exit 1
                fi
            else
                print_success "Coverage: ${COVERAGE_PCT}% (acceptable for release)"
            fi
        fi
    else
        print_error "Tests failed or coverage below threshold"
        exit 1
    fi

    # Update version and changelog if version changed
    if [[ "$NEW_VERSION" != "$CURRENT_VERSION" ]]; then
        echo ""
        print_step "Step 3: Updating version numbers..."
        update_manifest_version "$NEW_VERSION"
        print_success "Updated manifest.json to version ${NEW_VERSION}"

        echo ""
        print_step "Step 4: Updating CHANGELOG.md..."
        update_changelog "$NEW_VERSION"
    else
        print_warning "Skipping version updates (no version change)"
    fi

    # Git operations (only if --push flag is set)
    if [[ "$PUSH_TO_GIT" == "true" ]]; then
        echo ""
        print_step "Step 5: Git operations..."

        # Show git status
        echo ""
        git status --short
        echo ""

        # Commit changes
        print_step "  → Committing changes..."
        git add -A  # Add all changes (modified, deleted, and new files)
        git commit -m "Release version ${NEW_VERSION}" || print_warning "  Nothing to commit"

        # Create tag
        print_step "  → Creating tag v${NEW_VERSION}..."
        if git tag -a "v${NEW_VERSION}" -m "Release version ${NEW_VERSION}"; then
            print_success "  Created tag v${NEW_VERSION}"
        else
            print_warning "  Tag may already exist"
        fi

        # Push to GitHub
        # Skip pre-push hook since we already ran all checks (linting + tests) in Step 1 & 2
        # Note: --no-verify only skips LOCAL Git hooks - GitHub Actions CI will still run automatically
        print_step "  → Pushing to GitHub..."
        git push --no-verify origin main
        git push --no-verify origin "v${NEW_VERSION}"
        print_success "  Pushed to GitHub"
        print_step "  → GitHub Actions CI will run automatically on push (see .github/workflows/tests.yaml)"
    else
        echo ""
        print_warning "Skipping git operations (use --push flag to commit, tag, and push)"
    fi

    echo ""
    print_success "🎉 Release process complete!"
    echo ""
    echo "Summary:"
    echo "  Version: ${NEW_VERSION}"
    echo "  Linting: ✓"
    echo "  Tests: ✓"

    if [[ "$PUSH_TO_GIT" == "true" ]]; then
        echo ""
        echo "Next steps:"
        echo "  - GitHub Actions will automatically create the release from tag v${NEW_VERSION}"
        echo "  - Check https://github.com/mjcumming/wiim/releases for the new release"
    else
        echo ""
        echo "Next steps:"
        echo "  - Review changes: git diff"
        echo "  - Commit manually or run: $0 ${NEW_VERSION} --push"
    fi
}

# Run main function
main "$@"
