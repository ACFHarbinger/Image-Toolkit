"""C3 local web viewer (stdlib-only).

A localhost-only workspace viewer over the WorkspaceStore. Routes:

- GET /                  workspace home: investigations, sessions, plugins
- GET /session?path=...  one session's timeline + orphaned spans
- GET /investigation/N   one investigation's notes + linked sessions
- GET /compare?a=..&b=.. side-by-side A/B (evidence only; no winner)
- GET /artifact?path=... serve a raw artifact file (image/report)

Binds 127.0.0.1 by default and refuses 0.0.0.0. An ephemeral port is fine
(pass port=0 to auto-assign; the CLI prints the bound URL).
"""

from __future__ import annotations

import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

from ...host.store import WorkspaceStore
from ...model import Session

_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>
body{{font-family:system-ui,sans-serif;margin:2rem;color:#ddd;background:#16181d}}
a{{color:#7ab7ff}} table{{border-collapse:collapse;font-size:0.85rem}}
td,th{{border:1px solid #333;padding:2px 8px;text-align:left}}
h1,h2{{color:#fff}} .muted{{color:#888}} pre{{background:#0e1013;padding:1rem;overflow:auto}}
img{{max-width:48%;border:1px solid #333;background:#000}}
</style></head><body>{body}</body></html>"""


def _link(href: str, text: str) -> str:
    return f'<a href="{html.escape(href, quote=True)}">{html.escape(text)}</a>'


def render_home(store: WorkspaceStore) -> str:
    parts = ["<h1>devtool workspace</h1>"]

    parts.append("<h2>Investigations</h2>")
    invs = store.list_investigations()
    if invs:
        parts.append("<ul>")
        for inv in invs:
            parts.append(
                f"<li>{_link('/investigation/' + inv.name, inv.name)} "
                f"<span class='muted'>({inv.note_count} notes, {len(inv.sessions)} sessions)</span></li>"
            )
        parts.append("</ul>")
    else:
        parts.append("<p class='muted'>No investigations yet.</p>")

    parts.append("<h2>Sessions</h2>")
    sessions = store.sessions()
    if sessions:
        parts.append("<ul>")
        for s in sessions:
            parts.append(f"<li>{_link('/session?path=' + str(s), s.name)}</li>")
        parts.append("</ul>")
    else:
        parts.append("<p class='muted'>No telemetry sessions found.</p>")

    return _PAGE.format(title="devtool", body="".join(parts))


def _event_cells(e: dict) -> str:
    t = html.escape(f"{e.get('t', 0):.3f}")
    tid = html.escape(str(e.get("tid", "")))
    tname = html.escape(str(e.get("tname", "")))
    cat = html.escape(str(e.get("category", "")))
    ev = html.escape(str(e.get("event", "")))
    extra = html.escape(
        " ".join(f"{k}={v!r}" for k, v in e.items() if k not in ("t", "wall", "pid", "tid", "tname", "category", "event"))
    )
    return f"<tr><td>{t}</td><td>{tid}</td><td>{tname}</td><td>{cat}</td><td>{ev}</td><td class='muted'>{extra}</td></tr>"


def render_session(store: WorkspaceStore, path: str) -> str:
    session = Session.open(path)
    parts = [f"<h1>Session {html.escape(session.path.name)}</h1>"]
    parts.append(
        f"<p class='muted'>pid={session.pid} events={len(session.events)} "
        f"threads={len(session.thread_ids())} duration={session.duration:.3f}s</p>"
    )
    cats = ", ".join(f"{k}={v}" for k, v in sorted(session.category_counts().items()))
    parts.append(f"<p><b>Categories:</b> {html.escape(cats)}</p>")

    orphaned = session.orphaned_spans()
    if orphaned:
        parts.append(f"<h2>Orphaned spans ({len(orphaned)})</h2><ul>")
        for span in orphaned:
            parts.append(f"<li>{html.escape(repr(span))}</li>")
        parts.append("</ul>")

    parts.append(f"<h2>Timeline ({len(session.events)} events)</h2>")
    parts.append("<table><tr><th>t</th><th>tid</th><th>thread</th><th>category</th><th>event</th><th>fields</th></tr>")
    for e in session.events[-500:]:
        parts.append(_event_cells(e))
    parts.append("</table>")
    return _PAGE.format(title=session.path.name, body="".join(parts))


def render_investigation(store: WorkspaceStore, name: str) -> str:
    try:
        inv = store.open_investigation(name)
    except FileNotFoundError:
        return _PAGE.format(title="not found", body=f"<h1>No investigation named {html.escape(name)}</h1>")
    parts = [f"<h1>Investigation: {html.escape(inv.name)}</h1>"]
    parts.append("<h2>Notes</h2><ol>")
    for note in inv.notes():
        parts.append(
            f"<li><span class='muted'>{html.escape(note.get('t', ''))} {html.escape(note.get('author', ''))}</span>"
            f"<br>{html.escape(note.get('text', ''))}</li>"
        )
    parts.append("</ol>")
    parts.append("<h2>Linked sessions</h2><ul>")
    for s in inv.sessions:
        parts.append(f"<li>{_link('/session?path=' + s, s)}</li>")
    parts.append("</ul>")
    return _PAGE.format(title=inv.name, body="".join(parts))


def render_compare(store: WorkspaceStore, a: str, b: str) -> str:
    parts = ["<h1>Benchmark A/B</h1>", "<p class='muted'>Evidence only — no winner declared.</p>"]
    parts.append("<table style='width:100%'><tr>")
    for label, p in (("A", a), ("B", b)):
        if p and Path(p).exists():
            parts.append(f"<td style='width:50%'><h2>{label}</h2><img src='/artifact?path={html.escape(p, quote=True)}'></td>")
        else:
            parts.append(f"<td style='width:50%'><h2>{label}</h2><p class='muted'>missing: {html.escape(p)}</p></td>")
    parts.append("</tr></table>")
    return _PAGE.format(title="A/B compare", body="".join(parts))


class WebServer:
    """localhost-only workspace viewer."""

    def __init__(self, store: WorkspaceStore):
        self.store = store

    def handler(self) -> type:
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                from urllib.parse import parse_qs, urlparse

                parsed = urlparse(self.path)
                query = parse_qs(parsed.query)
                path = parsed.path
                if path == "/":
                    body = render_home(server.store)
                elif path == "/session":
                    body = render_session(server.store, query.get("path", [""])[0])
                elif path.startswith("/investigation/"):
                    body = render_investigation(server.store, path[len("/investigation/"):])
                elif path == "/compare":
                    body = render_compare(server.store, query.get("a", [""])[0], query.get("b", [""])[0])
                elif path == "/artifact":
                    self._serve_file(query.get("path", [""])[0])
                    return
                else:
                    self.send_response(404)
                    self.end_headers()
                    return
                payload = body.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def _serve_file(self, path: str) -> None:
                p = Path(path)
                if not p.exists() or not p.is_file():
                    self.send_response(404)
                    self.end_headers()
                    return
                data = p.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        return Handler

    def serve(self, host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
        if host == "0.0.0.0":
            raise ValueError("refusing to bind 0.0.0.0 (C3: localhost-only)")
        httpd = ThreadingHTTPServer((host, port), self.handler())
        return httpd


__all__ = ["WebServer", "render_home", "render_session", "render_investigation", "render_compare"]
