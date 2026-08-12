# HIE OpenCV Optional Extra — Chat

Date: 2026-08-12

Added the `restoration-opencv` optional middleware extra:

```bash
python3 -m pip install -e '.[restoration-opencv]'
```

It installs Pillow, NumPy, and `opencv-python-headless`, and exposes
`opencv_masked_inpainting_runner` with Telea or Navier–Stokes selection. Pillow
fallbacks remain available when the extra is not installed.
