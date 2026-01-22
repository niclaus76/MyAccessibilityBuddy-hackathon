#!/bin/bash
#
# Version Bump Script
# Usage: ./tools/bump-version.sh [major|minor|patch]
#
# This script updates version numbers across the project following SemVer.
# It updates: VERSION file, backend/__init__.py, backend/api.py
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

VERSION_FILE="$PROJECT_ROOT/VERSION"
BACKEND_INIT="$PROJECT_ROOT/backend/__init__.py"
BACKEND_API="$PROJECT_ROOT/backend/api.py"

# Read current version
if [ ! -f "$VERSION_FILE" ]; then
    echo "Error: VERSION file not found at $VERSION_FILE"
    exit 1
fi

CURRENT_VERSION=$(cat "$VERSION_FILE" | tr -d '[:space:]')

# Parse version components
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"

# Determine bump type
BUMP_TYPE="${1:-patch}"

case "$BUMP_TYPE" in
    major)
        MAJOR=$((MAJOR + 1))
        MINOR=0
        PATCH=0
        ;;
    minor)
        MINOR=$((MINOR + 1))
        PATCH=0
        ;;
    patch)
        PATCH=$((PATCH + 1))
        ;;
    *)
        echo "Usage: $0 [major|minor|patch]"
        echo "  major - Increment major version (breaking changes)"
        echo "  minor - Increment minor version (new features)"
        echo "  patch - Increment patch version (bug fixes)"
        exit 1
        ;;
esac

NEW_VERSION="$MAJOR.$MINOR.$PATCH"

echo "Bumping version: $CURRENT_VERSION -> $NEW_VERSION"

# Update VERSION file
echo "$NEW_VERSION" > "$VERSION_FILE"
echo "Updated: $VERSION_FILE"

# Update backend/__init__.py
if [ -f "$BACKEND_INIT" ]; then
    sed -i "s/__version__ = \"[0-9]*\.[0-9]*\.[0-9]*\"/__version__ = \"$NEW_VERSION\"/" "$BACKEND_INIT"
    echo "Updated: $BACKEND_INIT"
fi

# Update backend/api.py (multiple occurrences)
if [ -f "$BACKEND_API" ]; then
    sed -i "s/version=\"[0-9]*\.[0-9]*\.[0-9]*\"/version=\"$NEW_VERSION\"/g" "$BACKEND_API"
    sed -i "s/\"version\": \"[0-9]*\.[0-9]*\.[0-9]*\"/\"version\": \"$NEW_VERSION\"/g" "$BACKEND_API"
    echo "Updated: $BACKEND_API"
fi

echo ""
echo "Version bumped to $NEW_VERSION"
echo ""
echo "Next steps:"
echo "  1. Update CHANGELOG.md with changes for this version"
echo "  2. Commit changes: git add -A && git commit -m \"Bump version to $NEW_VERSION\""
echo "  3. Create tag: git tag -a v$NEW_VERSION -m \"Release version $NEW_VERSION\""
echo "  4. Push: git push && git push origin v$NEW_VERSION"
