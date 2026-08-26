# Registration gate recovery — 2026-08-26

Recovered the orphaned M2 registration telemetry and risk gate as default-off
additions. `ASP_REGISTRATION_GATE_ENABLED=1` is required to include the gate;
the calibrated ambiguity band reports `uncertain`, whose counterfactual default
is `prompt` for review. Hard BA/cycle/edge failures remain rejects. Crop
coverage is recorded but does not reject.

Recovered telemetry records graph components, per-pair evidence, BA residuals,
cycle closure, and pair-proposal evidence without changing matching or BA.
`bg_masked_matching` is included in the session config snapshot.

Verification: 20 targeted registration-telemetry, registration-gate, and
safety-policy tests passed; recovered modules compiled. No benchmark run.
