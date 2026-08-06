# Krita plugin (A1 pre-alpha)

The plugin requires Krita 5.2+ with Python 3.10+ and contains an English-only
offline placeholder lesson. Artwork review is not implemented yet.

**Do not use the Krita Snap.** Revision 109 (5.2.11) was inspected on Kubuntu
and omits Krita's Python plugin subsystem: no Python Plugin Manager, `pykrita`,
Scripter, or importer is bundled. Installing files into its confined data path
cannot enable a feature absent from the build. Use an official Linux AppImage,
which stores user plugins under `~/.local/share/krita/pykrita`.

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

The default target is `~/.local/share/krita/pykrita`. Use `--root PATH` only for
a different verified Krita user-data directory.

The docker reports whether packaged content and the standalone core are visible.
The AppImage's embedded Python should not be coupled to a repository virtual
environment. A2 must use an explicit local engine transport rather than editing
`sys.path` or assuming host visibility.
