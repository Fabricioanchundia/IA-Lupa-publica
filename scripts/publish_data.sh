#!/usr/bin/env bash
# Upload the public datasets (web/public/data/*.csv.gz) as a GitHub Release, which makes
# the "pages" workflow rebuild and publish the website. Run `uv run lupa export-public`
# first: that export is the privacy-checked, allowlisted data and nothing else is uploaded.
set -euo pipefail

files=(web/public/data/*.csv.gz)
if [ "${#files[@]}" -ne 8 ] || [ ! -e "${files[0]}" ]; then
  echo "Expected 8 files in web/public/data. Run: uv run lupa export-public" >&2
  exit 1
fi

tag="data-$(date +%Y-%m-%d)"
if gh release view "$tag" >/dev/null 2>&1; then
  echo "Release $tag exists: replacing its files"
  gh release upload "$tag" "${files[@]}" --clobber
else
  gh release create "$tag" "${files[@]}" \
    --title "Public data $(date +%Y-%m-%d)" \
    --notes "Public datasets for the website, exported with \`lupa export-public\` (allowlisted columns, privacy-checked)."
fi
gh workflow run pages.yml --ref main
echo "Website build started. Follow it with: gh run watch"
