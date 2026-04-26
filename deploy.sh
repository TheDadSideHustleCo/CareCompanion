#!/bin/bash
# deploy.sh — always run this instead of raw git push
# Auto-bumps SW cache version so the update banner fires for all users.

set -e

SW_FILE="sw.js"

# Read current version number
CURRENT=$(grep -oP 'carecompanion-v\K\d+' "$SW_FILE")
NEXT=$((CURRENT + 1))

# Bump it
sed -i "s/carecompanion-v${CURRENT}/carecompanion-v${NEXT}/" "$SW_FILE"
echo "SW bumped: v${CURRENT} → v${NEXT}"

# Stage sw.js alongside whatever else is staged
git add "$SW_FILE"

# Commit with caller-supplied message, or a default
MSG="${1:-Deploy: bump SW to v${NEXT}}"
git commit -m "$MSG

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"

git push
echo "Pushed (SW v${NEXT})"
