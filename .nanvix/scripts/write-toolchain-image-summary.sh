#!/usr/bin/env bash
# Copyright(c) The Maintainers of Nanvix.
# Licensed under the MIT License.
#
# Append a human-readable summary of the toolchain image update run to
# $GITHUB_STEP_SUMMARY.
#
# Required environment:
#   GITHUB_STEP_SUMMARY  Path to the summary file (set automatically on Actions)
# Optional environment:
#   TAG      Resolved tag, or empty if the resolve step failed
#   CHANGED  "1" if files were changed and a PR was opened/refreshed, else "0"
#   BRANCH   Automation branch name (used in the PR-opened message)

set -euo pipefail

: "${GITHUB_STEP_SUMMARY:?GITHUB_STEP_SUMMARY is required}"

{
    echo "## Nanvix Update Docker Image"
    echo ""
    echo "**Resolved tag:** \`${TAG:-<unresolved>}\`"
    echo ""
    if [ "${CHANGED:-0}" = "1" ]; then
        echo "Pull request opened or refreshed on \`${BRANCH:-<unknown>}\`."
    else
        echo "Already up to date — no changes required."
    fi
} >> "$GITHUB_STEP_SUMMARY"
