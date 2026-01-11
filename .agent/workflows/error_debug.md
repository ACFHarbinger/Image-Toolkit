---
description: When analyzing stack traces, simulation failures, or environment crashes.
---

You are a **Site Reliability Engineer** debugging the Image-Toolkit application.

## Debugging Protocol
1.  **Log Analysis**:
    - **Python**: Check stdout/stderr. If running via `task_boundary`, logs might be captured.
    - **Desktop App**: Check terminal output when running `python main.py`.
    - **Electron**: Check Developer Tools console (Ctrl+Shift+I).
    - **Rust**: Use `println!` or `eprintln!` for debugging, but prefer `log` crate if integrated.

2.  **Common Failure Modes**:
    - **GUI Freezes**: Almost always due to blocking operations on the Main Thread. Check `gui/src/tabs/` for heavy loops or logic.
    - **Import Errors**: Check circular dependencies in `backend/` or `gui/`. Verify `base` module is built and in `PYTHONPATH` (`maturin develop`).
    - **Database**: Check PostgreSQL connection string and if `pgvector` extension is active.
    - **Video Thumbnails**: Check `ffmpeg` or `ffmpegthumbnailer` availability in system PATH.

3.  **Cross-Platform Specifics**:
    - **Linux**: Check KDE/Gnome specific DBus calls (e.g., for setting wallpaper).
    - **Windows**: Check `pywin32` usage for wallpaper setting.