"""Knowledge Surface & Workspace Search Query Engine (Track D3 / #389).

Searches across:
- Durable Investigations (notes, metadata, attached git provenance).
- Telemetry Sessions (events, categories, payloads, error messages).
- Evaluation & Benchmark datasets (defect annotations, test case notes).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from ..host.store import WorkspaceStore


@dataclass
class SearchResult:
    """One matched item across the knowledge base."""

    source_type: str  # "investigation_note", "session_event", "eval_case", "investigation_meta"
    source_id: str  # name of investigation, pid, case id
    title: str
    snippet: str
    match_field: str
    path: Optional[str] = None


def _search_investigations(
    store: "WorkspaceStore", pattern: re.Pattern, max_results: int
) -> List[SearchResult]:
    results: List[SearchResult] = []
    for inv in store.list_investigations():
        if pattern.search(inv.name):
            results.append(
                SearchResult(
                    source_type="investigation_meta",
                    source_id=inv.name,
                    title=f"Investigation: {inv.name}",
                    snippet=f"Investigation container '{inv.name}' created at {inv.created_at}",
                    match_field="name",
                    path=str(inv.root),
                )
            )

        for _idx, note in enumerate(inv.notes()):
            text = note.get("text", "")
            author = note.get("author", "")
            if pattern.search(text) or pattern.search(author):
                snippet = text if len(text) <= 160 else text[:157] + "..."
                results.append(
                    SearchResult(
                        source_type="investigation_note",
                        source_id=inv.name,
                        title=f"Note in '{inv.name}' by @{author}",
                        snippet=snippet,
                        match_field="text",
                        path=str(inv.notes_path),
                    )
                )
            if len(results) >= max_results:
                return results
    return results


def _search_sessions(
    store: "WorkspaceStore", pattern: re.Pattern, max_results: int
) -> List[SearchResult]:
    results: List[SearchResult] = []
    for path in store.sessions():
        try:
            from ..model.session import Session

            session = Session.open(path)
        except Exception:
            continue

        for e in session.events:
            ev_name = str(e.get("event", ""))
            cat = str(e.get("category", ""))
            payload_str = " ".join(f"{k}={v}" for k, v in e.items() if k not in ("t", "wall", "pid", "tid"))

            if pattern.search(ev_name) or pattern.search(cat) or pattern.search(payload_str):
                snippet = f"[{cat}] {ev_name} (t={e.get('t', 0.0):.3f}s) {payload_str}"
                if len(snippet) > 160:
                    snippet = snippet[:157] + "..."
                results.append(
                    SearchResult(
                        source_type="session_event",
                        source_id=str(session.pid),
                        title=f"Telemetry Event in Session PID {session.pid}",
                        snippet=snippet,
                        match_field="event/payload",
                        path=str(session.path),
                    )
                )
                if len(results) >= max_results:
                    return results
    return results


def _search_evaluations(
    store: "WorkspaceStore", pattern: re.Pattern, max_results: int
) -> List[SearchResult]:
    results: List[SearchResult] = []
    eval_path = getattr(store, "repo_root", Path.cwd()) / "docs/website/public/data/asp_evaluations.json"
    if not eval_path.exists():
        return results
    try:
        data = json.loads(eval_path.read_text(encoding="utf-8"))
        for case_id, item in data.items():
            notes = str(item.get("notes", ""))
            defects = " ".join(str(d) for d in item.get("defects", []))
            if pattern.search(case_id) or pattern.search(notes) or pattern.search(defects):
                snippet = f"Case {case_id}: defects=[{defects}] notes='{notes}'"
                if len(snippet) > 160:
                    snippet = snippet[:157] + "..."
                results.append(
                    SearchResult(
                        source_type="eval_case",
                        source_id=case_id,
                        title=f"ASP Evaluation Case: {case_id}",
                        snippet=snippet,
                        match_field="notes/defects",
                        path=str(eval_path),
                    )
                )
                if len(results) >= max_results:
                    return results
    except Exception:
        pass
    return results


def search_workspace(
    term: str,
    store: "WorkspaceStore",
    category: str = "all",
    max_results: int = 50,
) -> List[SearchResult]:
    """Search the workspace knowledge base for term."""
    if not term:
        return []

    pattern = re.compile(re.escape(term), re.IGNORECASE)
    results: List[SearchResult] = []

    if category in ("all", "notes", "investigations"):
        results.extend(_search_investigations(store, pattern, max_results - len(results)))

    if len(results) < max_results and category in ("all", "events", "sessions"):
        results.extend(_search_sessions(store, pattern, max_results - len(results)))

    if len(results) < max_results and category in ("all", "evals", "benchmarks"):
        results.extend(_search_evaluations(store, pattern, max_results - len(results)))

    return results


def format_search_results(results: List[SearchResult], term: str, json_mode: bool = False) -> str:
    """Format search hits for CLI text output or JSON."""
    if json_mode:
        return json.dumps([asdict(r) for r in results], indent=2)

    if not results:
        return f"No results found for '{term}'."

    lines = [f"Search Results for '{term}' ({len(results)} matches):"]
    for r in results:
        lines.append(f"\n• [{r.source_type}] {r.title}")
        lines.append(f"  {r.snippet}")
        if r.path:
            lines.append(f"  location: {r.path}")
    return "\n".join(lines)


__all__ = ["SearchResult", "search_workspace", "format_search_results"]
