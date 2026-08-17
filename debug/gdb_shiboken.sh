#!/usr/bin/env bash
# Capture the app's real SIGSEGV/SIGABRT under gdb (the recurring wallpaper-restore
# crash inside Shiboken/PySide6). Stops at the first fatal signal, dumps the main
# thread bt plus every thread's bt, then lets gdb exit.
set -uo pipefail
cd /home/pkhunter/Repositories/Repos/Image-Toolkit
export HOME=/tmp/fakehome_gdb2
rm -rf /tmp/fakehome_gdb2
mkdir -p /tmp/fakehome_gdb2/.image-toolkit
ln -s /home/pkhunter/.image-toolkit/secrets /tmp/fakehome_gdb2/.image-toolkit/secrets
ln -s /home/pkhunter/.image-toolkit/telemetry /tmp/fakehome_gdb2/.image-toolkit/telemetry
ln -s /home/pkhunter/.image-toolkit/recovery /tmp/fakehome_gdb2/.image-toolkit/recovery
mkdir -p /tmp/fakehome_gdb2/.image-toolkit/logs

cat > /tmp/gdb_cmds.txt <<'GDBEOF'
set pagination off
set confirm off
set print thread-events off
handle SIGSEGV stop print nopass
handle SIGABRT stop print nopass
run
printf "\n=== APP STOPPED (fatal signal) ===\n"
bt
printf "\n=== ALL THREADS ===\n"
thread apply all bt
GDBEOF

timeout 100 gdb -q -batch -x /tmp/gdb_cmds.txt --args .venv/bin/python backend/main.py > debug/gdb_shiboken_out.log 2>&1
echo "gdb exit=$?"
