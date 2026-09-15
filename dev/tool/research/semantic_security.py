"""#398 research spike: conservative Python source-to-sink findings.

This is not a CodeQL/Joern replacement.  It exposes auditable candidate
findings that a future CPG engine can consume or confirm.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CandidateFinding:
    rule: str
    path: Path
    line: int
    message: str


def _name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def scan_python(path: Path) -> list[CandidateFinding]:
    """Find high-signal candidate sinks without executing or importing code."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
    except SyntaxError:
        return []
    findings: list[CandidateFinding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _name(node.func)
        shell = next((kw.value for kw in node.keywords if kw.arg == "shell"), None)
        if name in {"subprocess.run", "subprocess.call", "subprocess.Popen"} and isinstance(shell, ast.Constant) and shell.value is True:
            findings.append(CandidateFinding("shell-true", path, node.lineno, "subprocess call enables shell parsing"))
        elif name in {"pickle.load", "pickle.loads"}:
            findings.append(CandidateFinding("pickle-deserialization", path, node.lineno, "pickle deserialization requires trusted input"))
        elif name == "yaml.load" and not any(kw.arg == "Loader" and _name(kw.value).endswith("SafeLoader") for kw in node.keywords):
            findings.append(CandidateFinding("unsafe-yaml-load", path, node.lineno, "yaml.load has no SafeLoader"))
    return findings
