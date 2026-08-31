# ASP Phase 0.1 rating bundle — 2026-08-31

The inspector launches clean against the merged 97-case reference with an
offscreen smoke launch. Use:

```bash
cd submodules/ASP
PYTHONPATH=/home/pkhunter/Repositories/Repo/Image-Toolkit \
python backend/src/cli/eval_dispatch.py \
  --data-dir ~/Downloads/Data/Tests/asp-470-full97-20260831 \
  --results backend/benchmark/output/anime_stitch_20260831_023504.json \
  --out ~/Downloads/Data/Tests/asp-470-full97-20260831/asp_evaluations_20260831.json
```

The keyboard-first form saves ratings after every edit to the requested
`asp_evaluations_YYYYMMDD.json`; the human pass itself remains for Harbinger.

Comparator availability is incomplete: ASP and Simple resolve for all 97,
Hugin for 37, ground truth for 55, and Overmix for 0. The inspector handles
missing comparators, but a true five-way montage pass cannot happen until
the 97 Overmix renders are restored/regenerated. No corpus comparator run was
started.
