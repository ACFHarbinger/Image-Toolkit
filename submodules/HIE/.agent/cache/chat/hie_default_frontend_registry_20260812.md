# HIE Default Frontend Registry — Chat

Date: 2026-08-12

Added `build_default_pipeline()` for standalone frontends. It registers the
localized-retouching, global-tone, and crop-composition policies plus optional
matting and super-resolution adapters without loading model weights. The
PySide6 tab now starts with this registry and an untitled one-frame document,
so preview and explicit acceptance can be exercised immediately.
