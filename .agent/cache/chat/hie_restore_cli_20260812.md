# HIE Restoration CLI — Chat

Date: 2026-08-12

Added the `hie-restore` entry point for directly using HIE's local restoration
baselines:

```bash
uv sync --extra restoration-opencv
uv run hie-restore deblur input.png --output restored.png
uv run hie-restore inpaint owned.png --mask logo-mask.png --permission-confirmed
```

Inpainting selects OpenCV automatically when installed and otherwise falls
back to Pillow. Original files are preserved unless an explicit output path
overwrites them. Watermark/logo cleanup remains mask- and permission-gated.
