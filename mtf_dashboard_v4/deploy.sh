#!/usr/bin/env bash
# One-shot Cloudflare Pages deploy for the MTF Analytics dashboard.
#
# Usage:
#   ./deploy.sh                  # deploys to the production branch
#   ./deploy.sh --branch <name>  # deploys to a named preview branch
#
# Requires: wrangler (`npm i -g wrangler`) + `wrangler login` once.
set -euo pipefail
cd "$(dirname "$0")"

PROJECT="mtf"

if ! command -v wrangler >/dev/null; then
  echo "wrangler not found. Install with:  npm i -g wrangler" >&2
  exit 1
fi

echo "Deploying $(pwd) to Cloudflare Pages project '$PROJECT'..."
wrangler pages deploy . --project-name "$PROJECT" "$@"
