#!/usr/bin/env bash
# Run a command with the VS Code snap's environment undone.
#
# The snap terminal exports snap-private GTK_PATH, GIO_MODULE_DIR, LOCPATH,
# XDG_DATA_DIRS and similar. A webview launched from it loads the snap's old
# glibc into the system WebKit, and WebKitNetworkProcess dies with
# "__libc_pthread_init" ("WebKit encountered an internal error").
# VS Code keeps each original value in <NAME>_VSCODE_SNAP_ORIG; restore it.
# Outside the snap terminal this changes nothing.
set -euo pipefail
for orig in $(compgen -e | grep '_VSCODE_SNAP_ORIG$' || true); do
  name="${orig%_VSCODE_SNAP_ORIG}"
  value="${!orig}"
  if [ -n "$value" ]; then export "$name=$value"; else unset "$name"; fi
  unset "$orig"
done
for name in GTK_EXE_PREFIX GTK_PATH GIO_MODULE_DIR GTK_IM_MODULE_FILE GSETTINGS_SCHEMA_DIR LOCPATH; do
  case "${!name:-}" in *snap*) unset "$name" ;; esac
done
exec "$@"
