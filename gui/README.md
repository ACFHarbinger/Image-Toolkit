# Hybrid Image Editor (HIE) — PySide6 Desktop GUI (`gui/`)

This directory contains the **PySide6 (Qt for Python) desktop GUI** for the Hybrid Image Editor (HIE).

## Multi-Hosting Architecture
- **Embedded Mode:** Integrated directly into Image-Toolkit's PySide6 desktop GUI as a dedicated tab (`hie_tab.py`).
- **Standalone Mode:** Can be launched independently as a standalone PySide6 window application (`python -m hie.gui.main`).

## Capabilities
- Threaded `QThread` workers communicating off the main loop via Qt Signals & Slots.
- Native OpenGL / QGraphicsView viewport for image & video frame editing.
- Deep Learning & Reinforcement Learning interactive parameter control panels.
