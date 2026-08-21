"""Standalone HTML export: a session timeline that opens with no JS build.

Single self-contained file: inline CSS, an events table, category counts,
and orphaned spans. Consumers can open it in a browser or archive it.
"""

from __future__ import annotations

import html as _html
from typing import Any, Dict

from ..model.session import Session

_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>
body{{font-family:system-ui,sans-serif;margin:2rem;color:#ddd;background:#16181d}}
table{{border-collapse:collapse;font-size:0.8rem;width:100%}}
td,th{{border:1px solid #333;padding:2px 6px;text-align:left}}
h1,h2{{color:#fff}} .muted{{color:#888}}
</style></head><body>{body}</body></html>"""


def _event_row(e: Dict[str, Any]) -> str:
    t = _html.escape(f"{e.get('t', 0):.3f}")
    tid = _html.escape(str(e.get("tid", "")))
    tname = _html.escape(str(e.get("tname", "")))
    cat = _html.escape(str(e.get("category", "")))
    ev = _html.escape(str(e.get("event", "")))
    extra = _html.escape(
        " ".join(
            f"{k}={v!r}"
            for k, v in e.items()
            if k not in ("t", "wall", "pid", "tid", "tname", "category", "event")
        )
    )
    return f"<tr><td>{t}</td><td>{tid}</td><td>{tname}</td><td>{cat}</td><td>{ev}</td><td class='muted'>{extra}</td></tr>"


def session_to_html(session: Session) -> str:
    parts = [f"<h1>{_html.escape(session.path.name)}</h1>"]
    parts.append(
        f"<p class='muted'>pid={session.pid} events={len(session.events)} "
        f"threads={len(session.thread_ids())} duration={session.duration:.3f}s</p>"
    )
    cats = ", ".join(f"{k}={v}" for k, v in sorted(session.category_counts().items()))
    parts.append(f"<p><b>Categories:</b> {_html.escape(cats)}</p>")

    orphaned = session.orphaned_spans()
    if orphaned:
        parts.append(f"<h2>Orphaned spans ({len(orphaned)})</h2><ul>")
        for s in orphaned:
            parts.append(f"<li>{_html.escape(repr(s))}</li>")
        parts.append("</ul>")

    parts.append(f"<h2>Timeline ({len(session.events)} events)</h2>")
    parts.append("<table><tr><th>t</th><th>tid</th><th>thread</th><th>category</th><th>event</th><th>fields</th></tr>")
    for e in session.events:
        parts.append(_event_row(e))
    parts.append("</table>")
    return _PAGE.format(title=session.path.name, body="".join(parts))


__all__ = ["session_to_html"]
