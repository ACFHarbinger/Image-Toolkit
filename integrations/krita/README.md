# Krita plugin (A1 pre-alpha)

The current target is the owner's Krita 5.2.11 Snap on Kubuntu. The plugin
requires Krita 5.2+ with Python 3.10+ and contains an English-only offline
placeholder lesson. Artwork review is not implemented yet.

Install from the repository root while Krita is closed:

```bash
uv run python integrations/krita/install.py install
```

Restart Krita, enable **Cel-Shaded Learning Tutor** under
**Settings → Configure Krita → Python Plugin Manager**, restart if requested,
then show it through **Settings → Dockers → Cel-Shaded Learning Tutor**. Krita
places it on the right initially; it remains freely dockable.

Remove only this plugin with:

```bash
uv run python integrations/krita/install.py uninstall
```

The Snap installer target is
`~/snap/krita/current/.local/share/krita/pykrita`. Use `--root PATH` only for a
different verified Krita user-data directory.

The docker reports whether packaged content and the standalone core are visible.
Snap confinement may prevent importing a repository virtual environment; this
does not prevent the lesson shell from loading. A2 must use an explicit local
engine transport rather than editing `sys.path` or assuming host visibility.
