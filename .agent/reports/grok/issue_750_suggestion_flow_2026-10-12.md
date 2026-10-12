# Gate E suggestion path

Branch `dl-e-guidance-suggest`, off `review/dl-gate-e` (`1abd1169b`, draft #789). Codex held Gate E because nothing called `show_guidance()`.

- Review's **Suggest workflow changes** button builds a schema request from the captured workflow (the Diff & Apply source, otherwise the Generate filmstrip record). `advisor_trajectory()` is included when Review has one.
- The reply is parsed and validated against that same workflow. A valid or refused validation is shown in Diff & Apply. Text that does not parse stays a note.
- Local OCR is attached as `source: local` and resolved as a measurement. A model that claims that source is stripped. Other OCR/VLM evidence stays a model claim.
- Cloud suggest uses the existing preview-and-approve gate. The call runs off the GUI thread. Describe image still returns observations. Verdict buttons stay disabled.

Targeted checks: `test_guidance_request.py`, `test_guidance_vision.py`, and `test_guidance_evidence.py` (47); `test_guidance_suggest.py`, `test_guidance_diff_widget.py`, and `test_review_vision_tools.py` with `--run-gui` (34). No suite, benchmark, GPU, or live model. The comparison-pair loader is not this change. Gate E stays open.

— Grok, 2026-10-12
