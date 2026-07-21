#!/usr/bin/env bash
# Re-freeze the golden row/col counts after an INTENTIONAL output change.
cut -f3-5 "$(dirname "$0")/../output/MANIFEST.tsv" > "$(dirname "$0")/golden_manifest.tsv"
echo "re-froze tests/golden_manifest.tsv from output/MANIFEST.tsv"
