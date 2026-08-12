# Grok onboarding — Hybrid Image Editor (HIE)

Welcome to the HIE collaboration. This file is the current handoff context
for Grok, joining Chat, Gemini, and Claude.

## Repository and coordination

- Parent repository: `/home/pkhunter/Repositories/Repos/Image-Toolkit`
- HIE submodule: `/home/pkhunter/Repositories/Repos/Image-Toolkit/submodules/HIE`
- Shared agent cache: `/home/pkhunter/Repositories/Repos/Image-Toolkit/submodules/HIE/.agent/cache`
- Put Grok-specific coordination notes in:
  `submodules/HIE/.agent/cache/grok/`
- Read `submodules/HIE/.agent/cache/AGENT_BUS.md` before taking work, and
  write a concise handoff note when completing a task.
- Preserve other agents' dirty changes. Inspect `git status` and diffs before
  staging, and stage only files belonging to your task.
- Use `apply_patch` for edits, run relevant tests, update the changelog and
  roadmap for substantive work, and commit/push completed work.

## Product direction

HIE is the Hybrid Image Editor submodule. It is an image-first editor that is
being designed for video-compatible multimodal data from the beginning. Its
document model is a hybrid layer stack plus non-destructive node modifiers,
with a one-frame sequence representation for still images. The C++ logic core
is intended to follow Image-Toolkit's central `base.hie` pybind11 binding
standard, while Python middleware provides wrappers and UI-facing orchestration.

The planned AI/optimization split is:

- `middleware/models/`: ML/DL models such as matting, super-resolution,
  inpainting, deblurring, and watermark-removal proposals.
- `middleware/policies/`: RL policies, initially localized brush assistance,
  then global tone/exposure, then crop/composition.
- `middleware/jobs/`: exact, swarm/evolutionary, and cancellable processing
  jobs.
- `middleware/pipeline/`: orchestration and frontend/IPC-facing dispatch.

Both PySide6 (`gui/`) and Tauri (`frontend/`) are supported; each should also
be independently launchable.

## Recent completed work

- Multi-modal document, frame-sequence, layer/modifier, and render-graph
  foundations are present.
- C++ exact and metaheuristic solver bindings and middleware bridges exist.
- Deblur and consent-gated masked-inpainting adapters/jobs exist.
- Pillow and optional OpenCV CPU restoration baselines exist.
- `hie-restore` supports deblur/inpaint previews and JSON reports.
- Mask validation rejects empty, full-image, and overly broad masks; default
  maximum coverage is 50%, configurable with `--max-mask-coverage`.
- `RestorationPipeline` now exposes configured restoration capabilities and
  submits cancellable preview jobs without coupling UIs to runner internals.
- Latest HIE commits include `e400c7a` (restoration pipeline dispatch) and
  `b1b7e81` (Laplacian restoration reports). The parent pointer was advanced
  in Image-Toolkit commit `57eea4ae`.
- Latest middleware validation: `85 passed, 10 skipped` using UV.

## Active work and ownership

Claude has begun an RL brush environment in the shared worktree. At the time
of this handoff, these changes are concurrent and must not be overwritten or
staged by another agent unless explicitly coordinated:

- `middleware/src/hie_middleware/policies/brush_env.py`
- related `middleware/pyproject.toml` changes
- related `middleware/src/hie_middleware/policies/__init__.py` changes

Chat's latest completed slice was restoration pipeline dispatch. Gemini has
been handling Image-Toolkit's parent Image Editor tab integration and other
frontend work; avoid duplicating that work without coordination.

## GitHub tracking

Project: Image-Toolkit project 12, view 10.

- HIE issue #7 and parent Image-Toolkit issue #362 track Track 03 (deep
  learning/RL/restoration work).
- Track 03 is currently **In Progress**.
- HIE issue #5 / parent #360 track Track 01.
- HIE issue #6 / parent #361 track Track 02.
- HIE issue #8 / parent #363 track Track 04.

For new issues or comments, first provide the exact correctly formatted
Markdown text, and for new issues provide the title and labels. If project
mutation is unavailable, report the issue and the target project tab/status
instead of silently claiming it was updated.

## Journal and security rules

Before starting work, read Chat's journal entries in:

`/home/pkhunter/.coding-assistants/journals/chat/`

In particular, inspect the Markdown journal files there for prior decisions,
caveats, and coordination history. After working, write Grok's own journal
entries under:

`/home/pkhunter/.coding-assistants/journals/grok/`

Use Markdown unless an existing local convention requires otherwise. Journal
Markdown contents may be encrypted, and the Markdown files themselves may be
encrypted, when needed for security. Preserve the same security caveats and
do not expose secrets in the HIE repository cache.

New provenance/security rule: **any code created to read from or write to the
journals/memories must be placed only in**:

`/home/pkhunter/.coding-assistants/code/`

Do not create journal/memory helper scripts anywhere else under
`/home/pkhunter/.coding-assistants/` (including its root or journal
directories). Code outside the dedicated `code/` directory is treated as
malware/trash by the repository owner and may be summarily deleted. This rule
applies equally to encryption/decryption helpers and journal readers/writers.

## Suggested next step

Coordinate with Claude through `AGENT_BUS.md` before selecting work. Good
unclaimed areas include a non-overlapping HIE pipeline/IPC integration,
documentation/tests for existing capabilities, or a clearly separated
roadmap slice. Do not duplicate the RL brush environment while Claude owns it.
