#!/usr/bin/env bash
# Capture a real backtrace on the FIRST SIGSEGV in the app, distinguishing
# JVM-internal intentional faults from the real crash. We stop on SIGSEGV
# and immediately 'continue' the first few benign ones, then dump threads
# when the crash is inside Shiboken/Qt (the actual fault site).
set -u
cd /home/pkhunter/Repositories/Repos/Image-Toolkit
export HOME=/tmp/fakehome_gdb
rm -rf /tmp/fakehome_gdb
mkdir -p /tmp/fakehome_gdb/.image-toolkit
ln -s /home/pkhunter/.image-toolkit/secrets /tmp/fakehome_gdb/.image-toolkit/secrets
ln -s /home/pkhunter/.image-toolkit/telemetry /tmp/fakehome_gdb/.image-toolkit/telemetry
ln -s /home/pkhunter/.image-toolkit/recovery /tmp/fakehome_gdb/.image-toolkit/recovery
mkdir -p /tmp/fakehome_gdb/.image-toolkit/logs

gdb -q -batch \
  -ex "set pagination off" \
  -ex "handle SIGSEGV stop print nopass" \
  -ex "run" \
  -ex "echo \n=== CRASH SITE ===\n" \
  -ex "bt" \
  -ex "echo \n=== ALL THREADS ===\n" \
  -ex "thread apply all bt" \
  --args .venv/bin/python backend/main.py 2>&1 | grep -vE "WARNING: A restricted|WARNING: java|WARNING: Use --enable" > debug/gdb_sigsegv_out.log 2>&1
echo "gdb exit=$?"
