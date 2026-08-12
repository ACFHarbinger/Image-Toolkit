# HIE UV OpenCV Environment — Chat

Date: 2026-08-12

Added the optional OpenCV restoration environment through UV:

```bash
cd submodules/HIE/middleware
uv add --optional restoration-opencv 'Pillow>=10.0' 'numpy>=1.24' 'opencv-python-headless>=4.10'
uv run pytest -q
```

UV resolved and installed Pillow 12.3.0, NumPy 2.4.6, and
opencv-python-headless 5.0.0.93, and generated `middleware/uv.lock`. The
OpenCV inpainting integration test now runs when that extra is installed.
