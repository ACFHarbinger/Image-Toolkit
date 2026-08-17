#!/usr/bin/env bash
# Run the desktop app under gdb, capturing an all-thread backtrace the
# instant it crashes with SIGABRT, and leaving the process runnable under a
# debugger for any manual follow-up.
#
# This is the explicit "next step" both docs/TROUBLESHOOTING.md and
# .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md call for after
# sixteen-plus rounds of Python-level print/telemetry instrumentation
# narrowed the crash (QSocketNotifier warning -> glibc heap corruption ->
# SIGABRT, "corrupted size vs. prev_size") but never pinned down the exact
# native call responsible.
#
# IMPORTANT: this script deliberately does NOT stop on SIGSEGV, only
# SIGABRT. HotSpot JVMs raise SIGSEGV *on purpose* as part of normal
# operation -- implicit null-pointer checks and safepoint polling are both
# implemented by letting the CPU fault intentionally, then the JVM's own
# installed signal handler catches it and recovers (turns it into a
# NullPointerException, or just continues). An earlier version of this
# script stopped on SIGSEGV too, which made gdb intercept every one of
# these totally benign, JVM-internal signals -- producing a misleading
# "the app crashes before the login window even opens" symptom that never
# happens in normal, un-debugged execution. See Addendum 19 in
# .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md for the full
# story. SIGABRT is never used by the JVM for anything routine -- glibc's
# malloc_consolidate() only raises it on genuine heap corruption, which is
# exactly the "corrupted size vs. prev_size" symptom this tool exists for.
#
# Usage:
#   IMAGE_TOOLKIT_TELEMETRY=1 dev/run_with_gdb.sh
#   dev/run_with_gdb.sh --no-dropdown            # extra args forwarded to backend/main.py
#
# Output: an all-thread backtrace, written to
#   ~/.image-toolkit/telemetry/gdb-backtrace-<timestamp>.txt
# as soon as gdb catches SIGABRT -- correlate its timestamp against the
# matching telemetry-<pid>.jsonl file (enable telemetry too, per the usage
# line above) with dev/telemetry_analyzer.py to see exactly what
# Python-level event was in flight when the native fault happened.
#
# Also raises the core-dump size limit for this process tree (Addendum 20):
# a live SIGSEGV inside libQt6Core.so.6 was already resolved down to
# QObjectPrivate::deleteOrphaned()/::connect() via the stripped library's
# surviving dynamic symbol table, but `ulimit -c` defaulting to 0 meant
# neither crash actually wrote the core file hs_err's own output claimed it
# would -- with no core file, there's no way to inspect the actual damaged
# QObject/ConnectionData in a debugger. This script now sets it to
# unlimited so the *next* crash (if any) leaves one at
# ./core.<pid> (repo root, since that's this script's cwd).
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if ! command -v gdb >/dev/null 2>&1; then
    echo "gdb not found. Install it first (e.g. 'sudo apt install gdb')." >&2
    exit 1
fi

ulimit -c unlimited 2>/dev/null || echo "Warning: could not raise the core-dump size limit (ulimit -c unlimited failed) -- a crash won't leave a core file this run." >&2

OUT_DIR="$HOME/.image-toolkit/telemetry"
mkdir -p "$OUT_DIR"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BT_FILE="$OUT_DIR/gdb-backtrace-$TIMESTAMP.txt"

echo "🐍 Starting Python/PySide6 app under gdb..."
echo "   Backtrace-on-crash will be written to: $BT_FILE"
echo "   Core dump (if a crash happens) will land at: $(pwd)/core.<pid>"
echo "   (enable telemetry too: IMAGE_TOOLKIT_TELEMETRY=1, then correlate"
echo "    with: python dev/telemetry_analyzer.py)"

# shellcheck disable=SC1091
source .venv/bin/activate

# SIGSEGV: let it pass through untouched (nostop/noprint) -- the JVM uses it
# internally and recovers from it on its own; gdb must never break there.
# SIGABRT: stop and print -- this is the actual symptom ("corrupted size vs.
# prev_size" -> glibc abort()), never raised by the JVM for normal reasons.
# After dumping the backtrace, `continue` re-delivers the same SIGABRT to
# the inferior's OWN handler so the JVM's hs_err_pid<PID>.log still gets
# written for the same crash (gdb stopping first would otherwise silently
# suppress it) -- both diagnostics land side by side.
gdb -q -batch \
    -ex "set pagination off" \
    -ex "set confirm off" \
    -ex "handle SIGSEGV nostop noprint pass" \
    -ex "handle SIGABRT stop print" \
    -ex "run backend/main.py $*" \
    -ex "echo \n===== SIGABRT CAUGHT -- ALL-THREAD BACKTRACE =====\n" \
    -ex "thread apply all bt full" \
    -ex "echo \n===== RE-DELIVERING SIGNAL TO THE JVM'S OWN HANDLER (for hs_err_pid*.log) =====\n" \
    -ex "continue" \
    python 2>&1 | tee "$BT_FILE"

echo
echo "Backtrace (if any signal was caught) written to: $BT_FILE"

# The JVM writes hs_err_pid<PID>.log (and, now that ulimit -c is raised
# above, a core.<PID> file) to this script's cwd (the repo root) -- collect
# them into the same telemetry dir as everything else instead of leaving
# them as repo-root clutter.
shopt -s nullglob
hs_err_files=(hs_err_pid*.log core.[0-9]*)
if [ ${#hs_err_files[@]} -gt 0 ]; then
    mv "${hs_err_files[@]}" "$OUT_DIR/"
    echo "Moved JVM crash artifact(s) to: $OUT_DIR/"
    echo "  Resolve a Qt offset from one with:"
    echo "  python dev/resolve_qt_offset.py --hs-err $OUT_DIR/hs_err_pid<PID>.log"
fi
shopt -u nullglob
