# #474 Overmix comparator regeneration prep — 2026-08-31

## Readiness

`submodules/ASP/tools/bench/justfile` now runs `run_overmix.py` by file path.
The prior `-m backend.benchmark.run_overmix` form could resolve Image-Toolkit's
top-level `backend` package instead of ASP's; the script's own alias bootstrap
documents file-path execution as required. `--help` succeeds with the root venv.

The prerequisite is not installed: `vendor/Overmix` has no source checkout and
`vendor/Overmix/build/OvermixCli` is absent. Disk has 678 GiB free; the existing
full-97 corpus is 805 MiB.

## Authorization request

One serialized, monitored comparator corpus run is needed. It produces only the
smart-selected render used by the inspector; omit `--full` to avoid a second,
slower raw-frame pass.

```bash
cd /home/pkhunter/Repositories/Repo/Image-Toolkit
git submodule update --init vendor/Overmix
bash desktop/linux/scripts/setup_overmix.sh

source .venv/bin/activate
cd submodules/ASP
ASP_BENCH_THREAD_CAP=4 just bench::asp-run-overmix \
  --data-dir "$HOME/Downloads/Data/Tests/asp-470-full97-20260831" \
  --range 1-97
```

The setup downloads API-compatible wgpu-native `v0.19.4.1` and builds the
external GPL-3.0 `OvermixCli`; it is not linked into Image-Toolkit. The run
uses at most four OpenMP threads and has a five-minute timeout per case. Its
hard upper bound is 8h05m, so it must remain monitored and run alone; no GPU
models are loaded. Outputs are `output/overmix_stitch.png` and
`output/overmix_variant.json` per corpus case.

## #472 static eligibility

All 15 previously triaged `no_valid_edges` cases meet the new recovery guard
(`filter_output == 0` and retained frames >=2), so all reach the bounded
re-match call. This is path eligibility, not a quality claim: normal filters
remain authoritative.

| Cases | Retained frames | Newly adjacent pairs re-matched |
|---|---:|---:|
| 25, 34, 46, 50, 55, 66, 70, 76, 79, 90, 93 | 2 | 1 |
| 48, 52, 95 | 3 | 2 |
| 43 | 5 | 4 |

The five-case #472 slice did not contain a `no_valid_edges` case, so its
successful normal-path result does not substitute for an authorized corpus
measurement of the new branch.
