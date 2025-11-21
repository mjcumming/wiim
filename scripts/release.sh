#!/bin/bash
# WiiM Integration Release Script
# Automates the release process: linting, testing, versioning, changelog, and git operations

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

    # Ask for new version if not provided
    if [[ -z "$1" ]]; then
        echo -n "Enter new version (or press Enter to skip version bump): "
        read NEW_VERSION
    else
        NEW_VERSION=$1
    fi

    # Skip version bump if empty
    if [[ -z "$NEW_VERSION" ]]; then
        print_warning "Skipping version bump, using current version ${CURRENT_VERSION}"
        NEW_VERSION=$CURRENT_VERSION
    else
        # Validate version format (semver)
        if ! [[ "$NEW_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
            print_error "Invalid version format. Use semantic versioning (e.g., 0.3.0)"
            exit 1
        fi

        print_step "New version: ${NEW_VERSION}"
    fi

    echo ""
    print_step "Step 1: Running linting checks..."

    # Run ruff
    print_step "  → Running ruff..."
    if python -m ruff check custom_components/wiim/ --line-length 120; then
        print_success "  Ruff checks passed"
    else
        print_error "  Ruff checks failed"
        echo -n "Attempt auto-fix? (y/n): "
        read -r fix_choice
        if [[ "$fix_choice" == "y" ]]; then
            python -m ruff check custom_components/wiim/ --fix --line-length 120
            python -m ruff format custom_components/wiim/
            print_success "  Auto-fixed and formatted"
        else
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
    print_step "Step 2: Running tests..."
    if pytest tests/ --no-cov -q; then
        print_success "All tests passed"
    else
        print_error "Tests failed"
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
        echo "Please update CHANGELOG.md manually with release notes for version ${NEW_VERSION}"
        echo "Press Enter when done..."
        read -r
    else
        print_warning "Skipping version updates (no version change)"
    fi

    echo ""
    print_step "Step 5: Git operations..."

    # Show git status
    echo ""
    git status --short
    echo ""

    # Ask for confirmation
    echo -n "Commit and tag release? (y/n): "
    read -r commit_choice

    if [[ "$commit_choice" == "y" ]]; then
        # Commit changes
        print_step "  → Committing changes..."
        git add custom_components/wiim/manifest.json CHANGELOG.md
        git add custom_components/wiim/*.py  # Add any fixed linting issues
        git commit -m "Release version ${NEW_VERSION}" || print_warning "  Nothing to commit"

        # Create tag
        print_step "  → Creating tag v${NEW_VERSION}..."
        if git tag -a "v${NEW_VERSION}" -m "Release version ${NEW_VERSION}"; then
            print_success "  Created tag v${NEW_VERSION}"
        else
            print_warning "  Tag may already exist"
        fi

        # Ask about pushing
        echo ""
        echo -n "Push to GitHub (including tags)? (y/n): "
        read -r push_choice

        if [[ "$push_choice" == "y" ]]; then
            print_step "  → Pushing to GitHub..."
            git push origin main
            git push origin "v${NEW_VERSION}"
            print_success "  Pushed to GitHub"
        else
            print_warning "  Skipped push. Remember to push manually:"
            echo "    git push origin main"
            echo "    git push origin v${NEW_VERSION}"
        fi
    else
        print_warning "Skipped git operations"
    fi

    echo ""
    print_success "🎉 Release process complete!"
    echo ""
    echo "Summary:"
    echo "  Version: ${NEW_VERSION}"
    echo "  Linting: ✓"
    echo "  Tests: ✓"

    if [[ "$commit_choice" == "y" ]]; then
        echo ""
        echo "Next steps:"
        echo "  1. Go to https://github.com/mjcumming/wiim/releases"
        echo "  2. Create a new release from tag v${NEW_VERSION}"
        echo "  3. Copy relevant CHANGELOG.md entries to release notes"
    fi
}

# Run main function
main "$@"

