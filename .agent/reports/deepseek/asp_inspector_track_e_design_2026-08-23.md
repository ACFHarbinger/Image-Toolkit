# Track E — ASP Benchmark Inspector UX: Scoping & Design

**Document:** `.agent/reports/deepseek/asp_inspector_track_e_design_2026-08-23.md`
**Date:** 2026-08-23
**Status:** Scoping/design only — implementation after Harbinger review.
**Scope:** `submodules/ASP/backend/benchmark/evaluation/ui/` (the PySide6 rating
tool that produces `asp_evaluations.json`). Not the production pipeline.
**References:** bus 2026-08-23 "two new tracks" + "rename Coherence V2 tab"
posts; `evaluation/ui/{main_window,scoring_panel,shortcuts,queue_panel,image_panel,coherence_v2_tab}.py`;
`evaluation/{other/schema.py,constants/schema.py}`.

---

## 1. Per-comparator defect attribution (schema change)

### 1.1 Why
`RatingEntry.defects` is a flat `list[str]` (DEFECT_KEYS). `scoring_panel.py::toggle_defect`
mutates it with no comparator, so a tag can mean "ASP", "SCANS", "Hugin", or all
three — only the free-text `notes` disambiguates. That ambiguity is exactly what
made the known-good set mislabeling hard to catch today.

### 1.2 Proposed schema (backward compatible)
Keep `defects` as the **flat union** (so the benchmark consumer and every old
file keep working), and add an attribution map:

```json
{
  "asp": 3, "simple": 2, "defects": ["crop_loss", "seam_line"],
  "defect_attribution": {
    "asp": ["crop_loss"],
    "simple": ["seam_line"],
    "shared": ["crop_loss"]
  }
}
```

- `RatingEntry` gains `defect_attribution: dict[str, list[str]] = {}` keyed by
  `SCORABLE_KEYS` + `"shared"`. `defects` stays as the sorted union of all
  attributed keys, recomputed on save so the two never drift.
- `to_dict`: always emit `defects` (union) for old consumers; emit
  `defect_attribution` only when non-empty.
- `from_dict`: if `defect_attribution` present, parse it (validate comparator
  keys and DEFECT_KEYS); otherwise, treat a legacy flat `defects` list as
  **unattributed** → read as `{"shared": defects}`. **Never silently
  reinterpret a legacy tag as one specific comparator.** (Claude's requirement.)
- A new `defects` union field means the existing `_has_content` /
  `is_rated` logic and `bench_anime_stitch.py` defect consumers are unchanged.

### 1.3 UI
- The defect box becomes **comparator-scoped**: tags toggle onto the *focused*
  comparator (A/S/H/O focus ASP/Simple/Hugin/Overmix; `Tab` cycles). A small
  header shows the active target, defaulting to `shared`.
- Shortcuts stay `Ctrl+0..9` (ten numbered tags) + no shortcut for "Other", but
  they toggle onto the focused comparator. `Ctrl+Shift+0..9` toggles onto
  `shared` explicitly (so an ambiguity is recorded on purpose, not by accident).
- Optional live overlay (see §3): each comparator's image panel draws its
  attributed tags as colored chips, so "which panel has crop_loss" is visible
  at a glance.

---

## 2. Shortcuts (friction from a real rating pass)

Current map is solid (digits score focused panel; `[]=` preference; Space/Back
nav; Ctrl+S save). Two real gaps:

1. **Jump to a specific case** — `G` opens a small line edit (`asp_testNN`),
   uses the existing `session.go_to`/`open_dataset` path. High value: today the
   only way back to a case is walking the queue or clicking the list.
2. **Undo the last edit** — `Ctrl+Z`. The session has a *navigation* history
   (`_history`) but no *edit* undo. Design: keep a small in-memory stack of
   `(case_name, entry_snapshot)` captured in `main_window._commit` before each
   mutation; `Ctrl+Z` restores the most recent snapshot and reloads the panel.
   One-level is enough for a mis-hit; a 10-deep stack is cheap. (Fallback if we
   want to avoid the stack: `Ctrl+U` reloads the last *saved* version of the
   current case from disk — coarser but zero new state.)

Preference is already keyboard-only (`[]=`); confidence has no shortcut and
doesn't need one (secondary, and digits/Ctrl+digits are taken).

---

## 3. Interactive feature (one, not a redesign)

**Per-comparator defect-tag overlay** on the image panels: reuse
`image_panel.py` + `pixel_overlay.py`/`annotations.py` to draw a small colored
chip per attributed tag on each comparator's view. When a tag is toggled on
that comparator (or on `shared`), the chip appears immediately on all panels
that own it. This makes the per-comparator attribution (§1) legible while
rating, which is the point of the whole change.

Explicitly **not** in scope: new comparison modes (grid/filmstrip already
cover multi-image layout), re-skinning, gallery redesign.

---

## 4. Coherence V2 tab rename (inspector-only)

Drop "V2" in the inspector only. `ASP_COHERENCE_V2`, `src/rendering/compositing/
coherence_v2.py`, and `bench_coherence_v2_ab.py` are load-bearing/production and
stay untouched.

- Rename `ui/coherence_v2_tab.py` → `ui/coherence_tab.py`.
- `CoherenceV2Tab` → `CoherenceTab` (class docstring, `__all__`).
- UI strings: module docstring, title "✨ Coherence V2 Evaluator", "View Coherence
  V2 Only (B)", `ImagePanel("coherence_v2", "Coherence V2 A/B")`, and the four
  status strings in `coherence_tab.py` → drop "V2".
- `main_window.py`: `from .coherence_tab import CoherenceTab`; attribute
  `self.coherence_v2_tab` → `self.coherence_tab`; tab label → `"Coherence"`.
- File rename is worth it: the inspector is a leaf module, nothing else imports
  it (confirmed: only `main_window.py`).

---

## 5. Suggested implementation order (post-review)

1. `RatingEntry` schema + `from_dict`/`to_dict` backward-compat (unit tests:
   round-trip a legacy flat-defects file and a new attributed file).
2. `scoring_panel` comparator-scoped defect toggling + focused-target header.
3. `Ctrl+Z` undo stack in `main_window._commit` + `G` jump-to-case.
4. Per-comparator defect chip overlay on `image_panel`.
5. Coherence tab rename (mechanical).

All inspector-only; no production pipeline, no `ASP_*` flags, no change to
`bench_anime_stitch.py` defaults.
