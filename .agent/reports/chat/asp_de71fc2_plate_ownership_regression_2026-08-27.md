# ASP `de71fc2` — plate-ownership fix regresses black-background reconstruction — 2026-08-27

## TL;DR

1. **The "circular import blocking ASP test collection" is a wrong-CWD symptom, not a code defect.** Run ASP tests from the **Image-Toolkit root** (`pytest submodules/ASP/backend/test/`, per `pyproject.toml:192`), not from inside `submodules/ASP/`. From the root, collection succeeds — **1237 tests collected**.
2. **`de71fc2` ("fix(compositing): exclude warp padding from plate ownership") regresses one pre-existing test** it did not touch: `test_build_aligned_background_plate_reconstruction`. Rendering suite from the root: **1 failed, 287 passed**.
3. Parent commit `24fac26b` pins ASP at `de71fc2`, i.e. at a commit with a failing test, and **#463 sign-off is gated behind this fix**.

## The wrong-CWD "circular import"

Codex reported the ASP pytest command "blocked before collection by its existing `backend.src`/`asp_backend` circular import." Reproduced from `submodules/ASP/`:

```
_frame_utils.py:11   from asp_backend.alignment.canvas import _load_frames, _normalise_widths
  -> canvas.py:12    from backend.src.constants import CANVAS_MAX_DIM
     -> re-execs backend/src/__init__.py (as name "backend.src")
        -> core.pipeline -> _frame_utils -> asp_backend.alignment.canvas (partially initialised) -> ImportError
```

Root cause: ASP's `backend/src/` has **no `constants` or `errors` module** — `CANVAS_MAX_DIM` (and `errors.CanvasError`, `ECC_*`, etc.) live in the **parent Image-Toolkit** `backend/src/constants/animation.py`. The `from backend.src.constants import ...` imports scattered through ASP source are designed to resolve against the host repo via the shared `backend` namespace package (no `backend/__init__.py`). Run from inside `submodules/ASP/`, `backend.src` instead resolves to ASP's own tree, and the eager `__init__.py` → `core.pipeline` chain recurses through `_frame_utils` → `canvas` before `asp_backend` finishes initialising.

Run from the Image-Toolkit root, `backend.src.constants` resolves to the parent's real package and there is no recursion. `pytest submodules/ASP/backend/test/ --collect-only` → 1237 tests, clean.

**No code change needed for this.** It is an invocation-location issue. (A follow-up could make it fail loudly with a CWD hint, but nothing is broken.)

## The `de71fc2` regression

### What `de71fc2` changed

`_build_aligned_background_plate` in `backend/src/rendering/compositing/_plate_compositor.py`:

```python
-            m = bg
+            m = bg & (wf.max(axis=2) > 0)
```

A per-frame contribution mask now requires **confirmed background AND nonzero warped pixel content**. Intent: warped out-of-frame padding is `[0,0,0]` but the warped bg mask marks it as background, so the plate treated padding as a valid background sample and suppressed the baseline-canvas fallback (case-17's opaque horizontal bands).

### What it broke

`test_build_aligned_background_plate_reconstruction` (unmodified by `de71fc2`, green at `91ce862`, fails at `de71fc2`):

```python
bg_base = np.zeros((H, W, 3), dtype=np.uint8)
for r in range(H):
    bg_base[r, :, :] = (r * 2) % 255      # row 0 -> [0,0,0]; a legitimate black background row
...
bg0 = np.ones((H, W), dtype=bool); bg0[char_box] = False   # row 0 is confirmed background
...
plate, valid = _build_aligned_background_plate([f0, f1], [bg0, bg1], H, W)
assert valid.all()                        # FAILS: valid[0] is all-False
```

Row 0 is legitimately-black background content. `wf.max(axis=2) > 0` is `False` there, so row 0 is dropped from every contribution mask and `valid[0]` is all-False.

### Why it can't be fixed inside `_build_aligned_background_plate` as-is

Case-17's warp padding and this test's row 0 are **indistinguishable from the function's inputs**: both are `warped_bg == True` with pixel value `[0,0,0]`. `wf.max(axis=2) > 0` cannot satisfy "padding loses ownership" and "black background keeps ownership" simultaneously.

Note the `else` branch (no bg mask) already used `wf.max(axis=2) > 0` before `de71fc2` — the heuristic is not new; applying it in the branch where a real `bg` mask exists is what regressed.

A correct fix needs one of:
- **A geometric in-frame mask** passed in per frame — e.g. warp an all-ones sentinel through the same affine; `> 0` after warp = in-frame. New parameter, touches the call sites (`run_stage.py`, `_plate_builder.py`, `wallpaper_pipeline.py`).
- **An upstream correction** so `warped_bg` stops marking out-of-frame padding as background — fix the mask at the point it is warped, then `de71fc2`'s value check is unnecessary.

### Not validated

Confirming case-17 is actually fixed needs a regenerated render (benchmark-class). Not run here — the pytest-only working agreement does not cover renders.

## Recommendation

- **@Codex**: pick the in-frame-mask vs upstream-mask-fix approach with Harbinger; keep `test_build_aligned_background_plate_reconstruction` green and regenerate the case-17 review output for #463.
- **@Harbinger**: `24fac26b` currently pins ASP at a commit whose rendering suite is 1-red; `#463` sign-off depends on the corrected fix.
