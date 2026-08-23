#!/usr/bin/env bash
# Keep the registration telemetry benchmark alive one dataset at a time.
# A process crash or an uncaught per-dataset failure is retried before moving
# on, so a native OpenCV failure cannot discard the rest of the corpus.
set -u

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
data_dir="${ASP_DATA_DIR:-$HOME/Downloads/Data/Dump}"
log_dir="${ASP_MONITOR_LOG_DIR:-$repo_root/.agent/reports/codex}"
mkdir -p "$log_dir"

checkpoint="$repo_root/submodules/ASP/backend/benchmark/output/_checkpoint.json"
bench=(
  "$repo_root/submodules/ASP/backend/benchmark/bench_anime_stitch.py"
  --data-dir "$data_dir"
)

checkpoint_has() {
  local expected="$1"
  [ -f "$checkpoint" ] || return 1
  EXPECTED_NAME="$expected" CHECKPOINT_PATH="$checkpoint" \
    "$repo_root/.venv/bin/python" - <<'PY'
import json
import os
from pathlib import Path

try:
    rows = json.loads(Path(os.environ["CHECKPOINT_PATH"]).read_text())
except (OSError, json.JSONDecodeError):
    raise SystemExit(1)
raise SystemExit(0 if any(r.get("name") == os.environ["EXPECTED_NAME"] for r in rows if isinstance(r, dict)) else 1)
PY
}

for number in $(seq 70 97); do
  dataset="asp_test$(printf '%02d' "$number")"
  attempt=0
  while :; do
    attempt=$((attempt + 1))
    log="$log_dir/registration_telemetry_${dataset}.log"
    echo "[$(date --iso-8601=seconds)] starting $dataset attempt=$attempt" >> "$log"
    (
      cd "$repo_root" || exit 1
      source .venv/bin/activate
      ASP_BENCH_THREAD_CAP=1 \
      ASP_BENCH_RAM_ABORT_PCT=90 \
      ASP_DISABLE_PANORAMA_FALLBACK=1 \
      ASP_BENCH_UNGATED=1 \
      ASP_ALIGN_GATE_DX=9999 \
      ASP_COV_MIN_MULTI_PCT=0 \
      ASP_EXPERIMENT_LABEL=registration_telemetry_20260823 \
      ASP_RESOURCE_FLUSH_CUDA=1 \
      HF_HUB_OFFLINE=1 \
      TRANSFORMERS_OFFLINE=1 \
      PYTHONPATH="$repo_root" \
      PYTHONUNBUFFERED=1 \
      python "${bench[@]}" --tests "$dataset"
    ) >> "$log" 2>&1
    rc=$?
    if checkpoint_has "$dataset"; then
      echo "[$(date --iso-8601=seconds)] completed $dataset rc=$rc" >> "$log"
      break
    fi
    echo "[$(date --iso-8601=seconds)] retrying $dataset rc=$rc" >> "$log"
    sleep 5
  done
done
