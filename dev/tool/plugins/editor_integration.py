"""First-party Editor Integration plugin (Track C7 / D21).

Provides:
- Clipboard formatting for telemetry sessions, crash findings, and investigations
  into GitHub Markdown / PR description formats.
- IDE command templates and VS Code tasks for devtool workflows.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from ..host.plugins import Artifact, Channel, PluginManifest, Surface

MANIFEST = PluginManifest(
    name="editor_integration",
    version="0.1.0",
    description="Editor clipboard formatting, PR description generator, and IDE task templates.",
    surfaces=(
        Surface("cli", "export findings / sessions formatted for clipboard"),
        Surface("editor", "generate IDE task & command definitions"),
    ),
    channels=(
        Channel("editor_exports", "formatted clipboard buffers and task templates", retention="forever"),
    ),
    entry_point="tool.plugins.editor_integration:plugin",
)


class EditorIntegrationPlugin:
    manifest = MANIFEST

    def artifacts(self, store: Any) -> List[Artifact]:
        """Expose editor integration artifacts."""
        return []

    @staticmethod
    def format_session_markdown(session: Any) -> str:
        """Format a telemetry session summary as clean GitHub Markdown."""
        spans = session.spans()
        orphans = session.orphaned_spans()
        dur_ms = session.duration * 1000.0

        md = []
        md.append(f"### Telemetry Session `{session.pid}` Summary\n")
        md.append(f"- **Duration:** {dur_ms:.2f} ms ({session.duration:.2f} s)")
        md.append(f"- **Total Events:** {len(session.events)}")
        md.append(f"- **Reconstructed Spans:** {len(spans)}")
        md.append(f"- **Orphaned Spans:** {len(orphans)}")
        if session.truncated_final_line:
            md.append("- **Process Status:** ⚠️ Terminated abnormally (truncated JSONL line)")
        else:
            md.append("- **Process Status:** Clean exit")

        if orphans:
            md.append("\n#### In-Flight / Orphaned Spans at Termination\n")
            md.append("| Category | Span Name | Thread (TID) | Start Time |")
            md.append("| :--- | :--- | :--- | :--- |")
            for o in orphans:
                md.append(f"| `{o.category}` | `{o.name}` | {o.start_event.get('tname', '?')} ({o.tid}) | {o.start:.4f}s |")

        cat_counts = session.category_counts()
        if cat_counts:
            md.append("\n#### Event Category Breakdown\n")
            md.append("| Category | Count |")
            md.append("| :--- | :--- |")
            for cat, count in sorted(cat_counts.items(), key=lambda i: i[1], reverse=True):
                md.append(f"| `{cat}` | {count} |")

        return "\n".join(md)

    @staticmethod
    def format_investigation_markdown(inv: Any) -> str:
        """Format an Investigation container as a Markdown report for PRs or AGENT_BUS."""
        md = []
        md.append(f"## Investigation `{inv.name}`\n")
        md.append(f"- **Created:** {inv.created_at}")
        md.append(f"- **Updated:** {inv.updated_at}")
        if inv.sessions:
            sessions_str = ", ".join(f"`{Path(s).name}`" for s in inv.sessions)
            md.append(f"- **Linked Sessions:** {sessions_str}")

        notes = inv.notes() if callable(getattr(inv, "notes", None)) else []
        if notes:
            md.append("\n### Investigation Notes\n")
            for n in notes:
                md.append(f"- **[{n.get('t', '-')}] ({n.get('author', 'anonymous')}):** {n.get('text', '')}")

        return "\n".join(md)

    @staticmethod
    def generate_vscode_tasks() -> Dict[str, Any]:
        """Generate VS Code task definitions for the Development Tool.

        Invocation is ``python dev/`` (running the ``dev/`` directory, which
        Python resolves via ``dev/__main__.py``) rather than ``-m tool`` --
        the ``tool`` package has no ``__main__.py`` of its own since the
        2026-08-17 debug/dev fold moved it to a top-level ``dev/__main__.py``.
        """
        return {
            "version": "2.0.0",
            "tasks": [
                {
                    "label": "devtool: TUI Workbench",
                    "type": "shell",
                    "command": "python",
                    "args": ["dev/", "tui"],
                    "problemMatcher": [],
                    "group": "build",
                },
                {
                    "label": "devtool: Live Watch",
                    "type": "shell",
                    "command": "python",
                    "args": ["dev/", "watch"],
                    "problemMatcher": [],
                    "isBackground": True,
                },
                {
                    "label": "devtool: Local Web Inspector",
                    "type": "shell",
                    "command": "python",
                    "args": ["dev/", "web", "--port", "8088"],
                    "problemMatcher": [],
                    "isBackground": True,
                },
            ],
        }


plugin = EditorIntegrationPlugin()

def main(argv=None) -> int:
    """D52 command-plugin entry: python -m tool.plugins.<name> --stdio.

    Delegates to the shared stdio server so the host can spawn this plugin
    as a command entry (Grok lock #8: entry.command argv + --stdio).
    """
    from ..host.command import run_plugin_stdio

    return run_plugin_stdio(plugin, argv=argv)


if __name__ == "__main__":
    import sys

    sys.exit(main())

