# ASP stitch shortcut coverage — 2026-08-27

Added the configurable `Stitch` scope to the shared shortcut registry:
`Ctrl+Return` runs Stitch, `Esc` cancels, `F5` computes matches, and
`Ctrl+Shift+G` generates the SCANS comparison. The Stitch tab dispatches
through the existing buttons, retaining their enabled-state checks and making
all four bindings editable in the Settings shortcut UI.

Verification: shortcut-manager plus Stitch-tab focused tests: 19 passed, 2
expected skips. No benchmark or full-suite run.

The requested `gui/test/windows/` directory run remains pending explicit
Harbinger authorization under the resource rule.
