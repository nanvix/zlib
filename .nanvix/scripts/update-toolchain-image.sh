#!/usr/bin/env bash
# Copyright(c) The Maintainers of Nanvix.
# Licensed under the MIT License.
#
# Rewrite the pinned Nanvix toolchain image reference across the files
# tracked by this script. Emits `changed=0|1` to $GITHUB_OUTPUT.
#
# Required environment:
#   NEW_IMAGE      The new image reference (e.g. "ghcr.io/nanvix/toolchain-gcc:sha-abcdef0")
#   GITHUB_OUTPUT  Path to the step output file (set automatically on Actions)

set -euo pipefail

: "${NEW_IMAGE:?NEW_IMAGE is required}"
: "${GITHUB_OUTPUT:?GITHUB_OUTPUT is required}"

PATTERN='ghcr\.io/nanvix/toolchain-gcc:sha-[0-9a-f]{7,}'
TARGETS=(
    ".nanvix/z.py"
    ".github/workflows/nanvix-ci.yml"
)

CHANGED=0
for FILE in "${TARGETS[@]}"; do
    if [ ! -f "$FILE" ]; then
        echo "::warning::Skipping missing file: $FILE"
        continue
    fi
    if grep -qE "$PATTERN" "$FILE"; then
        # Portable in-place edit: GNU `sed -i` and BSD/macOS `sed -i ''`
        # have incompatible syntaxes, so use an explicit temp file and
        # `mv` instead.
        TMP="${FILE}.tmp.$$"
        sed -E "s|${PATTERN}|${NEW_IMAGE}|g" "$FILE" > "$TMP"
        mv "$TMP" "$FILE"
        if ! git diff --quiet -- "$FILE"; then
            echo "Updated: $FILE"
            CHANGED=1
        fi
    else
        echo "::warning::No image reference found in: $FILE"
    fi
done

echo "changed=${CHANGED}" >> "$GITHUB_OUTPUT"
