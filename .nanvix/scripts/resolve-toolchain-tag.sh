#!/usr/bin/env bash
# Copyright(c) The Maintainers of Nanvix.
# Licensed under the MIT License.
#
# Resolve the latest `sha-*` container tag for the Nanvix toolchain image
# published to GHCR and emit it via $GITHUB_OUTPUT.
#
# Required environment:
#   GH_TOKEN       Token used by `gh api` (must have read:packages on the org)
#   PACKAGE_OWNER  GHCR org/owner (e.g. "nanvix")
#   PACKAGE_NAME   Container package name (e.g. "toolchain-gcc")
#   IMAGE_NAME     Full image reference without tag (e.g. "ghcr.io/nanvix/toolchain-gcc")
#   GITHUB_OUTPUT  Path to the step output file (set automatically on Actions)
#
# Outputs written to $GITHUB_OUTPUT:
#   tag    The resolved `sha-<hex>` tag
#   image  `${IMAGE_NAME}:${tag}`

set -euo pipefail

: "${GH_TOKEN:?GH_TOKEN is required}"
: "${PACKAGE_OWNER:?PACKAGE_OWNER is required}"
: "${PACKAGE_NAME:?PACKAGE_NAME is required}"
: "${IMAGE_NAME:?IMAGE_NAME is required}"
: "${GITHUB_OUTPUT:?GITHUB_OUTPUT is required}"

# List container package versions for ${PACKAGE_OWNER}/${PACKAGE_NAME} and
# pick the most recently published one whose tag matches `sha-<hex>`.
# The GitHub API returns versions ordered newest-first; `--slurp` combines
# all paginated pages into a single JSON array so the `--jq` filter runs
# exactly once and emits a single tag (without `--slurp`, `--jq` runs per
# page and could emit multiple newline-separated values).
TAG=$(gh api \
    --paginate \
    --slurp \
    "/orgs/${PACKAGE_OWNER}/packages/container/${PACKAGE_NAME}/versions?per_page=100" \
    --jq '[.[][] | .metadata.container.tags[]?] | map(select(test("^sha-[0-9a-f]{7,}$"))) | .[0]')

if [ -z "$TAG" ] || [ "$TAG" = "null" ]; then
    echo "::error::Could not resolve a sha-* tag for ${IMAGE_NAME}"
    exit 1
fi

echo "tag=${TAG}" >> "$GITHUB_OUTPUT"
echo "image=${IMAGE_NAME}:${TAG}" >> "$GITHUB_OUTPUT"
echo "Resolved latest tag: ${TAG}"
