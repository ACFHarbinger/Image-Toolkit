#!/usr/bin/env bash
# Detached #30 ungated corpus runner. Survives TUI exit / cwd reset.
set -u
export PYTHONUNBUFFERED=1

IT_ROOT="/home/pkhunter/Repositories/Repos/Image-Toolkit"
ASP_ROOT="${IT_ROOT}/submodules/ASP"
PY="${IT_ROOT}/.venv/bin/python"
LOG="${IT_ROOT}/.agent/reports/grok/asp_ungated_97_detached.log"
PIDFILE="${IT_ROOT}/.agent/reports/grok/asp_ungated_97_detached.pid"
DUMP="${ASP_ROOT}/dump"

exec >>"${LOG}" 2>&1
echo "$$" > "${PIDFILE}"
echo "===== $(date -Is) detached ungated runner start pid=$$ ====="

# Wait only for a live Python bench, not this wrapper or a TUI command line.
while pgrep -f ".venv/bin/python .*backend/benchmark/bench_anime_stitch.py" >/dev/null 2>&1; do
  echo "$(date -Is) waiting for existing bench_anime_stitch.py ..."
  sleep 30
done

cd "${ASP_ROOT}" || exit 1
export ASP_BENCH_UNGATED=1
export ASP_ALIGN_GATE_DX=9999
export ASP_COV_MIN_MULTI_PCT=0
export ASP_EXPERIMENT_LABEL="${ASP_EXPERIMENT_LABEL:-post_m1_ungated}"
export ASP_BENCH_THREAD_CAP="${ASP_BENCH_THREAD_CAP:-4}"
export PYTHONPATH="${IT_ROOT}"

# Resume from incremental _checkpoint.json (dataset names already written).
# Do not use --skip-done: leftover 2026-08-07 panorama.png files would
# skip the rest of the corpus. Do not hardcode --range 2-97 without
# --resume-checkpoint — a watchdog relaunch used to redo completed work
# after SIGKILL (exit 137).
echo "$(date -Is) launching ungated run --range 2-97 --resume-checkpoint"
"${PY}" "${ASP_ROOT}/backend/benchmark/bench_anime_stitch.py" \
  --data-dir "${DUMP}" \
  --range 2-97 \
  --resume-checkpoint
status=$?
echo "$(date -Is) bench exit status=${status}"
exit "${status}"
