# HIE restoration pipeline dispatch — 2026-08-12

Added `middleware/pipeline/restoration.py` with `RestorationPipeline`, an
explicit operation/backend registry for cancellable deblur and masked-
inpainting preview jobs. It exposes capabilities for IPC/UI discovery and
keeps backend runner selection out of frontend code. Phase 3.11, changelog,
and middleware tests were updated. Claude's Phase 3.3 RL environment work was
not modified.
