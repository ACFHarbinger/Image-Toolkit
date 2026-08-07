# Krita plugin (learning alpha and C3 review)

The plugin requires Krita 5.2+ with Python 3.10+ and contains the first
English-only offline head-construction lesson plus exercise-document creation.
Landmark entry, redline rendering, and the complete review interaction are not
implemented yet.

**Do not use the Krita Snap.** Revision 109 (5.2.11) was inspected on Kubuntu
and omits Krita's Python plugin subsystem: no Python Plugin Manager, `pykrita`,
Scripter, or importer is bundled. Installing files into its confined data path
cannot enable a feature absent from the build. Use an official Linux AppImage,
which stores user plugins under `~/.local/share/krita/pykrita`.

Install from the repository root while Krita is closed:

```bash
uv run python integrations/krita/install.py install \
  --engine .venv/bin/cel-shaded-generator-engine
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
The AppImage's embedded Python is not coupled to a repository virtual
environment. The review boundary is a versioned, bounded, one-request JSON
process protocol exposed by `cel-shaded-generator-engine`; the plugin client
uses an explicit executable path or `CEL_SHADED_GENERATOR_ENGINE`, never
`sys.path`, a shell, or arbitrary operation names. UI configuration of that
path is still pending. The installer records the explicitly supplied executable
atomically at `${XDG_CONFIG_HOME:-~/.config}/cel-shaded-generator/krita.json`;
uninstalling the plugin deliberately preserves this reusable user setting.
Review, Accept, and Reject shortcuts default to unassigned. Configure them from
the tutor docker; values must be valid and unique, are saved atomically beside
the engine path, and only become active after the artist explicitly assigns
them. This avoids silently taking Krita's Tab canvas-only binding.

## Character Colors review checklist

The **Character Colors** Docker is currently in review and remains offline-only.
It authors portable style bibles, imports project-local references, creates
semantic material masks, and previews explicit palette roles. It never changes
source artwork or masks until the artist accepts a preview.

For a later live review, bind a portable project, import a reference, and verify
that the reference label, view type, and optional notes are editable. Create the
material masks, then optionally use variants such as `Material — hair — front`
and `Material — hair — back` using the Docker's **Create Material Mask Variant**
action. If two semantic materials overlap, preview must be
blocked with the conflicting material IDs and pixel counts. Correct the overlap
and preview again: a locked preview should appear under `Character Colors`.

Accepting must create an unlocked editable `Color — <material-id> — <role>`
layer; rejecting must remove only the owned preview. Source artwork and masks
must remain unchanged. A second preview cannot be created until the first is
accepted or rejected. Hosts exposing Krita node properties may also show the
originating `cel_shaded_generator.style_bible_id` metadata.

Project status rule: keep issue #17 in **In review** until all checks pass, then
move it to **Done**. If any expected behavior fails, document the step and move
it back to **In progress**. Issues #10, #11, and #12 remain in **In review**
until their existing live tutor checklists are performed.
