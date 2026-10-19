# Bug report: `solve_color_harmonization`'s `clamp_beta` double-corrects

Date: 2026-08-12
Found while: wiring `logic/src/{exact_solvers,metaheuristics}.cpp` into Image-Toolkit's
central `base` pybind11 module (see `hie_central_base_binding_20260812.md`) and smoke-testing
the resulting `base.hie.*` functions against known values.

## Repro (pure C++, no pybind11 involved — isolates it from my binding)

```cpp
LayerColorStats source{40.0f, 1.0f, 2.0f, 10.0f, 5.0f, 5.0f};
LayerColorStats target{60.0f, 3.0f, -2.0f, 20.0f, 15.0f, 10.0f};
auto result = solve_color_harmonization(source, target);
// alpha_l=2 beta_l=-80   (expected beta_l = target.mean_l - alpha_l*source.mean_l = -20)
// alpha_a=3 beta_a=2     (expected beta_a = 0)
// alpha_b=2 beta_b=7     (expected beta_b = -6)
```

The *initial* computation (`logic/src/exact_solvers.cpp:221-228`) is correct and matches the
documented formula exactly. The bug is in `clamp_beta` (`exact_solvers.cpp:230-238`):

```cpp
auto clamp_beta = [&](float alpha, float& beta, float src_min, float src_max,
                      float out_min, float out_max) {
    float lo = alpha * src_min + beta;
    float hi = alpha * src_max + beta;              // computed once, with the ORIGINAL beta
    if (lo < out_min) beta += out_min - lo;          // beta changes here...
    if (hi > out_max) beta -= hi - out_max;           // ...but `hi` above is now stale
};
```

`hi` is computed once before either branch runs. If the lower-bound branch fires and adjusts
`beta`, the upper-bound check still uses the *original* `hi`, so when both bounds are violated
(which happens whenever `alpha` scales the source range wider than the output range — e.g. any
`alpha > 1`, since a doubled dynamic range around a shifted mean almost always overshoots both
ends) the corrections stack instead of composing correctly, producing a `beta` a full
`(hi_original - out_max)` further off than intended.

Worked example (L channel above): initial `beta=-20`. `lo=-20 < 0` → `beta += 20` → `beta=0`.
`hi` is still `180` (computed from the old `beta=-20`) → `180 > 100` → `beta -= 80` → `beta=-80`.

## Why I didn't just fix it

`logic/` is Gemini's lane per `AGENT_BUS.md`'s boundaries, and this is nontrivial: for
`alpha` far from 1, no `beta` (a pure shift) can satisfy *both* bounds simultaneously — the
scaled range is simply wider than the output range, so "non-clipping" is only achievable for
`alpha` close to 1 no matter how `clamp_beta` is written. Recomputing `hi` after the first
correction (`hi = alpha * src_max + beta;` inserted before the second `if`) fixes the *sequencing*
bug and makes the result deterministic and closer to correct, but doesn't remove the
fundamental "impossible for large alpha" case — that's a genuine design question (clip? rescale
alpha too? accept partial clipping?) worth Gemini's or Harbinger's call, not mine to decide
unilaterally in someone else's file.

## What I did instead

Left `call_hie_exact_solver`'s pure-Python reference implementation
(`middleware/src/hie_middleware/jobs/exact_dp.py`) as the only implementation wired up — it
never had `clamp_beta` in the first place (I didn't port a non-clipping guarantee I didn't have
a confirmed-correct spec for), so it's unaffected. `middleware/src/hie_middleware/
logic_bridge/solvers.py` (the native adapter) deliberately does NOT expose
`solve_seam`/`solve_color_harmonization`, only `pso_solve`/`de_solve` (verified correct — see
the other cache note), specifically so nothing accidentally regresses to the buggy native
color-harmonization path.
