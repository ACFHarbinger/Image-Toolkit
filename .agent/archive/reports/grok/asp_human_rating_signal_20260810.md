# ASP human rating signal (mid-pass) — Grok note

**Date:** 2026-08-10  
**From:** Grok, after Harbinger’s live rating feedback  
**Context:** Concurrent human coherence rating pass via `just asp-benchmark-assess`

## Observed (Harbinger)

- After module pruning/refactor, ASP coherence is **better than pre-prune**, but still
  **loses to OpenCV SCANS (simple)** on nearly all rated cases so far.
- SCANS failure mode: usually **mild ghosting**.
- ASP failure modes: **banding**, **color shifts**, **degraded/visible seam lines**
  across multiple stitches.

Early JSON snapshot (`asp_evaluations_20260810.json`, first tests) already shows
`preference: "simple"` with higher simple coherence than ASP (e.g. test01 ASP 3 vs
Simple 4; crop_loss defects). Generator narrative:
“Human ratings currently prefer OpenCV SCANS (simple) more often than ASP.”

## Implication (not a full ASP redesign proposal yet)

Automated metric summaries in the last full corpus run (e.g. `anime_stitch_20260807_045552`)
can still show mixed/comparable automated verdicts and even higher ASP sharpness —
**that does not contradict** human structural preference for SCANS. Dashboard must
keep **human vs automated panels strictly labeled**.

Likely ASP submodule focus areas (for later deep dive with ASP team):

1. Photometric / color consistency after warp (color shifts).
2. Seam blending / multi-band / gain compensation (banding + seam visibility).
3. Fallback policy: if human-coherent SCANS is better, default product path may
   need “prefer simple when structure fails” more aggressively — without hiding
   ASP research progress.
4. Do **not** optimize solely for SSIM/sharpness if human coherence is the V1 bar.

## Docs website follow-up (done this pass)

- `generate-dashboard-data.mjs` aggregates 9 automated runs + latest human JSON.
- Ratings dashboard shows human signal banner + automated multi-run table.
- Refresh: `just dashboard-data` then `cd docs/website && npm run dev` → `/dashboard/ratings`.

## Ask for Harbinger (when rating pass pauses)

- Approximate N rated so far and rough preference split (ASP vs simple vs tie).
- Worst 5 / best 5 test IDs for an ASP war-room backlog.
- Whether “ship Hybrid: SCANS-safe default + ASP experimental” is acceptable
  product framing for IT users while ASP quality work continues.
