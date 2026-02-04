#!/bin/bash
# Push this project to https://github.com/jbeats13/cat.git
# Usage: ./push_to_github.sh   (or: bash push_to_github.sh)

set -e
REPO_URL="https://github.com/jbeats13/cat.git"

cd "$(dirname "$0")"

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "Not a git repo. Run this from the cat project root."
  exit 1
fi

if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$REPO_URL"
else
  git remote add origin "$REPO_URL"
fi

echo "Pushing to $REPO_URL ..."
git push -u origin main
