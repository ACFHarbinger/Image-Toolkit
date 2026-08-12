# HIE Restoration Jobs — Chat

Date: 2026-08-12

Added `submit_restoration_job` and `RestorationResult` under
`middleware/jobs/restoration.py`. The job boundary supports injected deblur
and mask-guided inpainting runners, cooperative cancellation/progress, and
structured failure when no optional runtime is configured. It requires a mask
and permission confirmation for watermark inpainting.

Documentation updated:

- `docs/moon/CHANGELOG.md`
- `docs/moon/ROADMAP.md`
- `docs/moon/roadmaps/03_deep_learning_and_rl_subsystem.md`
