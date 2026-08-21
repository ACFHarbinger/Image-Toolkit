#!/usr/bin/env python3
"""Python source parser/ingestion plugin (#423).

A D52 command plugin: spawned by the host as
".venv/bin/python dev/plugins/py_parser/parser.py --stdio" (Grok lock #8:
the manifest's entry.command is the argv; the host appends --stdio). Speaks
the frozen JSON-RPC-over-stdio contract (initialize / list_artifacts /
list_records / ping) and answers with REAL evidence about a workspace's
Python sources:

- list_artifacts -> one artifact per scanned .py file, #410 shape
  {kind, name, path, meta}; meta carries {language, loc, symbols:[...]}.
- list_records   -> devtool.record-shaped records (#409): one record per
  extracted symbol (kind="symbol") plus one per file (kind="file").

Parsing uses the standard library ast module -- the language's own parser,
zero dependencies, no tree-sitter. Symbols: functions, async functions,
classes, module-level imports, and module-level assignments.

Scan root: the first non-flag argument after --stdio, else cwd (the host
spawns command plugins from the workspace root).
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PROTOCOL_VERSION = "1"
SERVER_NAME = "py_parser"
SERVER_VERSION = "0.1.0"
EXTENSIONS = {".py"}
IGNORED_DIRS = {".git", ".venv", "__pycache__", "node_modules", "target", "build", "dist", ".tox"}

RECORD_SCHEMA = "devtool.record"
RECORD_SCHEMA_VERSION = 1


def scan_root_from_argv(argv: List[str]) -> Path:
    """--root <dir> or cwd (--stdio is always present from the host)."""
    root = Path.cwd()
    if "--root" in argv:
        idx = argv.index("--root")
        if idx + 1 < len(argv):
            root = Path(argv[idx + 1])
    return root


def _iter_python_files(root: Path) -> List[Path]:
    out: List[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in EXTENSIONS:
            continue
        if any(part in IGNORED_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        out.append(path)
    return out


def _symbols_from_tree(tree: ast.Module) -> List[Dict[str, Any]]:
    """Extract {name, kind, line} for functions/classes/imports/assigns."""
    symbols: List[Dict[str, Any]] = []

    def visit(node: ast.AST) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append({"name": node.name, "kind": "function", "line": node.lineno})
        elif isinstance(node, ast.ClassDef):
            symbols.append({"name": node.name, "kind": "class", "line": node.lineno})
        elif isinstance(node, ast.Import):
            for alias in node.names:
                symbols.append({"name": (alias.asname or alias.name).split(".")[0], "kind": "import", "line": node.lineno})
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                symbols.append({"name": alias.asname or alias.name, "kind": "import", "line": node.lineno})
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id.isidentifier() for t in node.targets):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    symbols.append({"name": target.id, "kind": "assignment", "line": node.lineno})
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            symbols.append({"name": node.target.id, "kind": "assignment", "line": node.lineno})
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(tree)
    return symbols


def _scan(root: Path) -> Dict[str, Any]:
    """{files: [{path, rel, loc, symbols}], symbols: [records]}."""
    files: List[Dict[str, Any]] = []
    symbols: List[Dict[str, Any]] = []
    for path in _iter_python_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError):
            tree = None
        syms = _symbols_from_tree(tree) if tree is not None else []
        files.append(
            {
                "path": str(path),
                "rel": str(path.relative_to(root)),
                "loc": text.count(chr(10)) + 1,
                "symbols": syms,
            }
        )
        for s in syms:
            s = dict(s)
            s["file"] = str(path.relative_to(root))
            symbols.append(s)
    return {"files": files, "symbols": symbols}


class PyParserServer:
    """JSON-RPC-over-stdio server for Python sources (D52)."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._cache: Optional[Dict[str, Any]] = None

    def _data(self) -> Dict[str, Any]:
        if self._cache is None:
            self._cache = _scan(self.root)
        return self._cache

    def _list_artifacts(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for f in self._data()["files"]:
            out.append(
                {
                    "kind": "source_file",
                    "name": f["rel"],
                    "path": f["path"],
                    "meta": {
                        "language": "python",
                        "loc": f["loc"],
                        "symbols": f["symbols"],
                    },
                }
            )
        return out

    def _list_records(self) -> List[Dict[str, Any]]:
        workspace = str(self.root)
        records: List[Dict[str, Any]] = []
        for s in self._data()["symbols"]:
            records.append(
                {
                    "schema": RECORD_SCHEMA,
                    "schema_version": RECORD_SCHEMA_VERSION,
                    "kind": "symbol",
                    "start_ms": 0.0,
                    "end_ms": None,
                    "source": SERVER_NAME,
                    "workspace": workspace,
                    "payload": {
                        "name": s["name"],
                        "symbol_kind": s["kind"],
                        "line": s["line"],
                        "file": s["file"],
                        "language": "python",
                    },
                }
            )
        for f in self._data()["files"]:
            records.append(
                {
                    "schema": RECORD_SCHEMA,
                    "schema_version": RECORD_SCHEMA_VERSION,
                    "kind": "file",
                    "start_ms": 0.0,
                    "end_ms": None,
                    "source": SERVER_NAME,
                    "workspace": workspace,
                    "payload": {
                        "file": f["rel"],
                        "language": "python",
                        "loc": f["loc"],
                        "symbol_count": len(f["symbols"]),
                    },
                }
            )
        return records

    def handle(self, raw: str) -> Optional[str]:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
        if not isinstance(msg, dict) or "id" not in msg:
            return None
        method = msg.get("method")
        msg_id = msg["id"]
        if method == "initialize":
            return json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": PROTOCOL_VERSION,
                        "capabilities": {"artifacts": True, "records": True},
                        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                    },
                }
            )
        if method == "list_artifacts":
            return json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": {"artifacts": self._list_artifacts()}})
        if method == "list_records":
            return json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": {"records": self._list_records()}})
        if method == "ping":
            return json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": {}})
        return json.dumps(
            {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"method not found: {method}"},
            }
        )

    def serve_stdio(self, stdin=None, stdout=None) -> None:
        stdin = stdin or sys.stdin
        stdout = stdout or sys.stdout
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            response = self.handle(line)
            if response is not None:
                stdout.write(response + chr(10))
                stdout.flush()


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--stdio" not in argv:
        print("py_parser: --stdio is required (Grok lock #8: the host appends it)", file=sys.stderr)
        return 2
    root = scan_root_from_argv(argv)
    PyParserServer(root).serve_stdio()
    return 0


if __name__ == "__main__":
    sys.exit(main())
