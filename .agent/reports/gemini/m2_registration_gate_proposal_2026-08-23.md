# Draft: M2 Registration-Risk Gate — Updated Proposal

**Status:** Discussion draft. No implementation authorization. Supersedes the
framing in Codex's `m2_graph_consistency_gate_proposal_2026-08-22.md` with
updated context from the 2026-08-23 Harbinger brainstorm session.  
**Author:** Agy  
**Decisions required from Harbinger:** four, marked **[DECISION]** below.

---

## 1. Problem Statement (Updated)

The M2 discriminating exit criterion requires:

> Safe ASP must select Raw ASP on ≥1 known-good case AND SCANS on every known
> catastrophe. Always-SCANS is not M2 success.

Every combination of the three existing gates (SeamVis, Ghost, Composite) fails
this bar on the current corpus. Root cause confirmed: all three gates measure
**rendered-output photometric properties**; their audited correlations with
human judgment are inverse or absent (SeamVis rho +0.43 is the only positive
signal, but threshold-sweeping found zero `(floor, ratio)` pairs that separate
test96 from all six catastrophes).

**New context from Harbinger (2026-08-23 brainstorm):**

1. **Catastrophe failure modes:** most are misalignment/duplicate-strip
   registration failures. Color shifts and ghosting are secondary artifacts
   of the same misalignment (bad alignment → bad background-plate estimate →
   color bleed and ghosting at strip edges). A registration-stage gate is
   therefore well-targeted at the actual failure mechanism.

2. **test96 is not the only known-good constraint.** The bar is "any known-good
   case," and §15.3 shows the corpus has a **10 / 38 / 49** preference split
   (Raw ASP preferred / tie / SCANS preferred). The gate needs to correctly
   classify ≥1 of 10 known-good cases as low-risk. test96 being hard does not
   block M2 exit if any other known-good case separates cleanly.

3. **test96's confounding SeamVis score is explained.** Both ASP and SCANS
   show severe cropping on test96; the human rated it acceptable. SeamVis
   (sv=32.2) is likely flagging the crop boundary as a seam discontinuity, not
   an internal misalignment artifact. Severe crop loss can follow from
   conservative canvas sizing after *successful* registration — in which case
   RANSAC metrics would be clean and the registration gate would correctly
   classify test96 as low-risk.

4. **Several catastrophes also show severe crop loss.** This is the primary
   discrimination risk: if crop-loss catastrophes have clean registration
   metrics similar to test96, the gate would incorrectly classify them as
   low-risk. The probe must resolve this.

---

## 2. Proposed Gate Architecture

### 2.1 Registration-Risk Gate (pre-render, replaces Ghost + Composite)

| Signal | Already in JSON? | Description |
|:---|:---:|:---|
| `filtered_edges / raw_edges` ratio | ✅ Partial | Global match-inlier proxy; low ratio → many rejected pairs |
| `affine_health.ratio` + `.valid` | ✅ | Alignment consistency; hard validity check |
| `alignment.dy_cv` / `dx_cv` | ✅ | CV of per-strip displacement; high → inconsistent |
| Per-pair RANSAC inlier count | ❌ Missing | Fraction of matches surviving RANSAC per strip pair |
| Per-pair reprojection RMS | ❌ Missing | RMS reprojection residual after RANSAC per pair |
| Bundle-adjustment residual | ❌ Missing | Global BA residual after all-pairs solve |
| Transform cycle inconsistency | ❌ Missing | `T_ij ∘ T_jk ∘ T_ki` error for graph loops (≥3 strips) |

The partial signals in today's JSON (filtered/raw ratio, `affine_health`,
`dy_cv`/`dx_cv`) provide a starting point. The three missing signals are the
most directly correlated with registration quality and require instrumentation
before the probe run.

### 2.2 Classification

Three classifications, recorded in the run manifest with contributing reasons:

- `low_risk` → select Raw ASP
- `uncertain` → default policy applies (see §2.3)
- `high_confidence_failure` → select SCANS; named reason logged

A hard validity failure (`affine_health.valid = False`, disconnected matching
graph) escalates directly to `high_confidence_failure` without passing through
the weighted score.

### 2.3 Uncertainty Policy

**[DECISION A — Harbinger]** The current M2 wording says uncertainty selects
SCANS. The proposal adds an `uncertain_result_policy` setting:

- `scans` — current M2 wording; conservative default
- `raw_asp` — prefer Raw ASP when uncertain
- `prompt` — HITL: show both outputs, score, and reasons; user decides

Since the uncertain region is expected to be small, the HITL `prompt` option
has low user-friction cost and is the only guaranteed-terminating fallback if
the gate cannot classify a case with confidence. Needs roadmap amendment and
Harbinger sign-off before code.

### 2.4 SeamVis Relationship

SeamVis (rho +0.43) remains a **separate rendering-stage backstop**:

- Registration gate: pre-render, detects misalignment / duplicate-strip risk
- SeamVis: post-render, detects visible seam discontinuities

They are complementary and should not be merged. Known blind spot not addressed
here: color-shift failures caused by background-plate estimation independently
of registration quality (`ASP_HOLD_BG_SUB` path).

---

## 3. Probe Protocol

**[DECISION B — Harbinger]** Approve the 97-case corpus re-run with new
registration telemetry instrumented (~2.5–3h on a 3090).

### 3.1 Instrumentation Required

Add to `bench_anime_stitch.py` output:

```json
"matching": {
  "raw_edges": ...,
  "filtered_edges": ...,
  "per_pair_inlier_counts": [...],     // NEW — int per matched pair
  "per_pair_reprojection_rms": [...]   // NEW — float per matched pair
},
"alignment": {
  "affines": ...,
  "ba_residual_rms": 0.0,              // NEW — global BA residual after solve
  "dy_cv": ..., "dx_cv": ...
}
```

These fields should be available from existing `_bundle_adjust_affine`
internals and the RANSAC step — instrumentation, not new computation.

### 3.2 Evaluation Protocol

From Codex's Proposal B, adapted:

1. **Calibration split:** from the structural red set, keep every uniquely-
   represented defect type in calibration; hold out examples only from
   defect types represented more than once.
2. **Calibrate** fixed, interpretable weights on the calibration slice only.
3. **Freeze** the rule — no further tuning against the full red set.
4. **Evaluate** on the held-out slice → full red set → all 97 cases.

### 3.3 Discriminating Bar Check

The probe passes if:

- Gate classifies **≥1 of the 10 Raw-ASP-preferred cases** as `low_risk`
- Gate classifies **all 6 catastrophes** as `uncertain` or
  `high_confidence_failure`

**[DECISION C — Harbinger]** Confirm the bar applies to any of the 10
known-good cases, not specifically test96. This allows test96 to be
`uncertain` without failing M2 exit, as long as one other known-good case
is correctly classified.

### 3.4 Primary Discrimination Risk

Several catastrophes show severe crop loss — the same surface characteristic
as test96. If any of those catastrophes also show clean registration metrics
(good RANSAC, low BA residual), the gate classifies them as `low_risk` →
selects Raw ASP → fails the bar. The probe resolves whether this actually
occurs.

**[DECISION D — Harbinger]** If the probe finds a crop-loss catastrophe with
clean registration metrics, which fallback:

- **(a)** Add a crop-coverage signal as a secondary gate input (penalize cases
  where both ASP and SCANS drop below a coverage floor, regardless of
  registration quality)
- **(b)** Expand the red set with more crop-loss examples before claiming
  generalization
- **(c)** Route crop-loss `uncertain` cases through the HITL `prompt` path

Option (a) is the most principled — crop-loss cases where both outputs are
heavily cropped are structurally distinct from well-cropped misalignment
failures, and a coverage floor is already computed in today's metrics.

---

## 4. What This Does Not Address

- Corpus expansion before generalization claims (M2.5a scope)
- `cqas_v2` redesign (M2.5a scope)
- Ensemble / learned gate (out of scope until interpretable baseline exists)
- Video (out of scope)

---

## 5. Decision Summary

| # | Decision | Default if not decided |
|:---:|:---|:---|
| **A** | Approve `uncertain_result_policy` amendment (add `prompt` HITL option) | Uncertainty → SCANS (current wording) |
| **B** | Approve 97-case re-run with instrumentation | No probe; status quo |
| **C** | Confirm bar applies to any of the 10 known-good cases | Ambiguous |
| **D** | Fallback if crop-loss catastrophe has clean registration | Decide after probe results |

---

## 6. Authorship

- **Brainstorm:** Claude (framing), Codex (Proposal A/B/C/D),
  Harbinger (answers to 7 questions, 2026-08-23 session)
- **This document:** Agy synthesis. Not implementation authorization.
- **Next step:** Harbinger sign-off on Decisions A–C → Codex instruments and
  re-runs the corpus.
