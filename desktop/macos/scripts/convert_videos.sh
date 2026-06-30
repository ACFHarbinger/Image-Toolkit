#!/bin/bash
# Delegates to the Linux counterpart — no macOS-specific changes needed.
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec bash "$REPO_ROOT/desktop/linux/scripts/convert_videos.sh" "$@"
