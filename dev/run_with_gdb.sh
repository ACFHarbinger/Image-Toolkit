#!/usr/bin/env bash
# Run the desktop app under gdb, capturing an all-thread backtrace the
# instant it crashes with SIGABRT or SIGSEGV, and leaving the process
# runnable under a debugger for any manual follow-up.
#
# This is the explicit "next step" both docs/TROUBLESHOOTING.md and
# .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md call for after
# sixteen-plus rounds of Python-level print/telemetry instrumentation
# narrowed the crash (QSocketNotifier warning -> glibc heap corruption ->
# SIGABRT, "corrupted size vs. prev_size"; separately, a shiboken binding-
# hash SIGSEGV during MainWindow construction/teardown, Addenda 29-31) but
# never pinned down the exact native call responsible.
#
# HISTORY (why this now stops on SIGSEGV too): an earlier version of this
# script let SIGSEGV pass through untouched, because the app used to embed
# a JVM (JPype cryptography module) whose HotSpot runtime raises SIGSEGV
# *on purpose* for implicit null-pointer checks and safepoint polling, and
# recovers from it internally -- stopping gdb there just intercepted totally
# benign, JVM-internal signals (see Addendum 19). Issue #435 replaced that
# JVM module with a native C/OpenSSL implementation, so the process has no
# embedded JVM left to raise benign SIGSEGVs (or to convert a real fatal one
# into its own SIGABRT+hs_err, which is how earlier rounds' SIGSEGV crashes
# ended up caught here at all). Passing SIGSEGV through untouched post-#435
# would mean a real native SIGSEGV now gets zero diagnostics -- the opposite
# of what this tool is for -- so it stops and prints like SIGABRT.
#
# Usage:
#   IMAGE_TOOLKIT_TELEMETRY=1 dev/run_with_gdb.sh
#   dev/run_with_gdb.sh --no-dropdown            # extra args forwarded to backend/main.py
#   RUN_ARGS="dev/repro_guest_startup.py" dev/run_with_gdb.sh   # alternate inferior target
#
# Output: an all-thread backtrace, written to
#   ~/.image-toolkit/telemetry/gdb-backtrace-<timestamp>.txt
# as soon as gdb catches SIGABRT/SIGSEGV -- correlate its timestamp against
# the matching telemetry-<pid>.jsonl file (enable telemetry too, per the
# usage line above) with dev/telemetry_analyzer.py to see exactly what
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

# SIGSEGV and SIGABRT: stop and print both -- post-#435 there's no embedded
# JVM left to raise SIGSEGV for benign reasons (see header), and SIGABRT is
# the glibc heap-corruption symptom ("corrupted size vs. prev_size") this
# tool was originally built for. After dumping the backtrace, write a real
# core file of the inferior via `generate-core-file` BEFORE re-delivering the
# signal. This is the crucial step every prior round assumed happened but
# never did: with `ulimit -c` raised, the kernel core is *still* piped to
# apport (`/proc/sys/kernel/core_pattern` -> `/usr/share/apport/apport`), and
# once gdb is attached the kernel never writes a core at all because gdb owns
# the signal -- so a file named core.<pid> never materialized despite hs_err
# claiming it would. The gdb-generated core captures the corrupted heap (the
# whole point: inspecting the damaged QObject/ConnectionData) at the exact
# stop. `continue` re-delivers the same signal to the inferior's own default
# handler so the process still terminates the way it normally would.
gdb -q -batch \
    -ex "set pagination off" \
    -ex "set confirm off" \
    -ex "handle SIGSEGV stop print" \
    -ex "handle SIGABRT stop print" \
    -ex "run ${RUN_ARGS:-backend/main.py} $*" \
    -ex "echo \n===== SIGNAL CAUGHT -- ALL-THREAD BACKTRACE =====\n" \
    -ex "thread apply all bt full" \
    -ex "echo \n===== WRITING CORE FILE (kernel core_pattern pipes to apport; gdb owns the signal, so generate-core-file is the only way a core lands) =====\n" \
    -ex "generate-core-file $OUT_DIR/core.$TIMESTAMP" \
    -ex "echo \n===== RE-DELIVERING SIGNAL TO THE INFERIOR'S DEFAULT HANDLER =====\n" \
    -ex "continue" \
    python 2>&1 | tee "$BT_FILE"

echo
echo "Backtrace (if any signal was caught) written to: $BT_FILE"

# Historical artifact collection: the embedded JVM (removed in #435) used to
# write hs_err_pid<PID>.log to this script's cwd on a fatal SIGSEGV; that
# path is gone now, but collect any straggler core.<PID> the kernel manages
# to write anyway (e.g. if core_pattern isn't apport-piped on some machine)
# into the same telemetry dir instead of leaving it as repo-root clutter.
shopt -s nullglob
stray_cores=(core.[0-9]*)
if [ ${#stray_cores[@]} -gt 0 ]; then
    mv "${stray_cores[@]}" "$OUT_DIR/"
    echo "Moved stray kernel core dump(s) to: $OUT_DIR/"
fi
shopt -u nullglob
