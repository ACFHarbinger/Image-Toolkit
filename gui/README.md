# Hybrid Image Editor (HIE) — PySide6 Desktop GUI (`gui/`)

This directory contains the **PySide6 (Qt for Python) desktop GUI** for the Hybrid Image Editor (HIE).

## Multi-Hosting Architecture
- **Embedded Mode:** Image-Toolkit re-exports `HieEditorTab` from this package
  (`from hie_gui import HieEditorTab`). Parent thin wrappers live under
  `Image-Toolkit/gui/src/tabs/editor/` and must not re-implement the UI.
- **Standalone Mode:** Launch with `hie-gui` or `python -m hie_gui.main [--image PATH]`.

## Capabilities
- Threaded `QThread` workers communicating off the main loop via Qt Signals & Slots.
- Native OpenGL / QGraphicsView viewport for image & video frame editing.
- Deep Learning & Reinforcement Learning interactive parameter control panels.

## Running

Install the GUI and the local middleware package, then launch the standalone
window:

```bash
python3 -m pip install -e ../middleware -e .
hie-gui
# or: python3 -m hie_gui.main
```

`HieTab` is the embeddable widget. Standalone mode starts with the dependency-
light Phase 1 policy registry and an untitled one-frame document, so its
preview/accept workflow is immediately demonstrable without model weights. A
host can replace the registry and provide its active `DocumentHistory` with
`set_history()`. Assistance is previewed first and only accepted through an
explicit action.

Hosts that need one stateful integration object can use middleware's
`PipelineSession`, which combines the active history with the shared proposal
registry and acceptance service.
