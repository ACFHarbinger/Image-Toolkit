"""D5 reproducibility artifacts: one-click investigation bundles (#391).

'devtool bundle <investigation> [--include-captures]' emits a portable
folder (or zip) artifact containing the investigation's manifest, notes,
a repro script that re-runs the captured command, and (only with
--include-captures) the telemetry JSONL + run sidecars. D20 redaction:
large / crash captures stay local unless explicitly included.

'devtool repro --from-bundle <artifact>' re-runs the captured command
under the same telemetry and writes a new investigation for the replayed
run.

Bundle layout (the on-disk contract):

    <name>/manifest.json      -- the investigation manifest (D20 content)
    <name>/notes.jsonl        -- annotations (append-only)
    <name>/repro.sh           -- re-runs the captured command (exec line)
    <name>/gdb-backtrace.txt  -- present only if the investigation had one
    <name>/captures/          -- ONLY with --include-captures
        telemetry-<pid>.jsonl
        <session>.run.json    -- run sidecars (command/cwd/env/exit)

A bundle is a plain directory unless zip_out=True, which produces
<name>.zip. The replay path accepts either a folder or a zip.
"""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .store import WorkspaceStore

MANIFEST_FILENAME = "manifest.json"
NOTES_FILENAME = "notes.jsonl"
REPRO_FILENAME = "repro.sh"
GDB_FILENAME = "gdb-backtrace.txt"
CAPTURES_DIR = "captures"
RUN_SUFFIX = ".run.json"


@dataclass
class BundleResult:
    """One built bundle artifact."""

    path: Path
    investigation: str
    include_captures: bool
    command: List[str]
    cwd: str
    n_sessions: int = 0
    n_captures: int = 0


def _iter_run_sidecars(inv: Any) -> List[Path]:
    """All .run.json sidecars the investigation's linked sessions have."""
    out: List[Path] = []
    seen = set()
    for session_rel in inv.sessions:
        sp = Path(session_rel)
        if not sp.is_absolute():
            sp = Path(inv.root) / session_rel
        side = sp.with_suffix(sp.suffix + RUN_SUFFIX)
        if side.exists() and side not in seen:
            seen.add(side)
            out.append(side)
    return out


def _recover_from_sidecar(side: Path) -> Optional[tuple[List[str], str]]:
    """(command, cwd) from one run sidecar, or None if it has no command."""
    try:
        data = json.loads(side.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    run = data.get("run", {})
    cmd = list(run.get("command", []) or [])
    if cmd:
        return cmd, str(run.get("cwd", ""))
    return None


def _first_repro_command(inv: Any, store: WorkspaceStore) -> tuple[List[str], str]:
    """Recover the command + cwd from the first run sidecar that has one.

    Linked-session sidecars first (D1 convention), then any sidecar stored
    directly inside the investigation folder (e.g. repro.run.json written
    by cmd_repro when no telemetry session was produced).
    """
    for side in _iter_run_sidecars(inv):
        hit = _recover_from_sidecar(side)
        if hit:
            return hit
    for side in sorted(inv.root.rglob("*" + RUN_SUFFIX)):
        if not side.is_file():
            continue
        hit = _recover_from_sidecar(side)
        if hit:
            return hit
    return [], ""


def _repro_script(command: List[str], cwd: str) -> str:
    """POSIX shell script re-running the captured command from its cwd."""
    lines = [
        "#!/bin/sh",
        "# Reproduced from a Development Tool D5 bundle (#391).",
        "# Re-run: sh repro.sh   (IMAGE_TOOLKIT_TELEMETRY=1 is set here)",
        "set -e",
        "cd " + (shlex.quote(cwd) if cwd else "."),
        "export IMAGE_TOOLKIT_TELEMETRY=1",
        "exec " + " ".join(shlex.quote(str(a)) for a in command),
    ]
    return "\n".join(lines) + "\n"


def build_bundle(  # noqa: C901
    store: WorkspaceStore,
    name: str,
    *,
    include_captures: bool = False,
    dest_dir: Optional[Path] = None,
    zip_out: bool = True,
) -> BundleResult:
    """Bundle one investigation into a portable artifact (D5).

    Always includes manifest + notes + repro script (D20-safe); telemetry
    JSONL + run sidecars only when include_captures is set.
    """
    inv = store.open_investigation(name)
    command, cwd = _first_repro_command(inv, store)

    dest_dir = Path(dest_dir) if dest_dir is not None else Path.cwd()
    bundle_name = name if not name.endswith(".zip") else name[:-4]
    folder = dest_dir / bundle_name
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True, exist_ok=True)

    # 1. Manifest + notes (D20 content).
    (folder / MANIFEST_FILENAME).write_text(
        json.dumps(inv.manifest, indent=2), encoding="utf-8"
    )
    notes_path = inv.notes_path
    if notes_path.exists():
        shutil.copy2(notes_path, folder / NOTES_FILENAME)

    # 2. Repro script.
    if command:
        (folder / REPRO_FILENAME).write_text(
            _repro_script(command, cwd), encoding="utf-8"
        )

    # 3. gdb backtrace if present.
    gdb_src = inv.root / GDB_FILENAME
    if gdb_src.exists():
        shutil.copy2(gdb_src, folder / GDB_FILENAME)

    # 4. Captures (D20 redaction: only when explicitly requested).
    n_captures = 0
    if include_captures:
        cap_dir = folder / CAPTURES_DIR
        cap_dir.mkdir(exist_ok=True)
        copied = set()
        for session_rel in inv.sessions:
            sp = Path(session_rel)
            if not sp.is_absolute():
                sp = Path(inv.root) / session_rel
            for p in (sp, sp.with_suffix(sp.suffix + RUN_SUFFIX)):
                if p.exists() and p.is_file() and p not in copied:
                    shutil.copy2(p, cap_dir / p.name)
                    copied.add(p)
        # Also sweep in-folder captures (defensive); the notes log is
        # already at the bundle root, so keep it out of captures/. Note
        # Path.suffix of "x.run.json" is ".json", hence the endswith check.
        for p in sorted(inv.root.rglob("*")):
            if p.name == NOTES_FILENAME:
                continue
            if p.is_file() and p not in copied and (p.suffix == ".jsonl" or p.name.endswith(RUN_SUFFIX)):
                shutil.copy2(p, cap_dir / p.name)
                copied.add(p)
        n_captures = len(copied)
        if n_captures == 0:
            cap_dir.rmdir()

    out_path = folder
    if zip_out:
        zip_path = dest_dir / (bundle_name + ".zip")
        if zip_path.exists():
            zip_path.unlink()
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(folder.rglob("*")):
                if p.is_file():
                    zf.write(p, bundle_name + "/" + str(p.relative_to(folder)))
        shutil.rmtree(folder)
        out_path = zip_path

    return BundleResult(
        path=out_path,
        investigation=name,
        include_captures=include_captures,
        command=command,
        cwd=cwd,
        n_sessions=len(inv.sessions),
        n_captures=n_captures,
    )


def extract_bundle(artifact: Path, workdir: Optional[Path] = None) -> Path:
    """Expand a bundle artifact (folder or zip) into *workdir*; return the
    expanded folder root (the folder that holds manifest.json)."""
    artifact = Path(artifact)
    if artifact.is_dir():
        return artifact
    if not artifact.exists():
        raise FileNotFoundError("bundle artifact not found: " + str(artifact))
    workdir = Path(workdir) if workdir is not None else Path(tempfile.mkdtemp(prefix="devtool-bundle-"))
    workdir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(artifact, "r") as zf:
        zf.extractall(workdir)
    # Manifest-driven root discovery: the zip carries a <name>/ prefix, so
    # find whichever folder actually holds manifest.json (avoids guessing
    # when captures/ is the only subdirectory).
    candidates = [workdir]
    candidates += [p for p in sorted(workdir.iterdir()) if p.is_dir()]
    for cand in candidates:
        if (cand / MANIFEST_FILENAME).exists():
            return cand
    raise ValueError("bundle artifact has no manifest.json: " + str(artifact))


def replay_bundle(artifact: Path, store: WorkspaceStore) -> Dict[str, Any]:
    """Re-run the captured command from a bundle under telemetry, writing a
    new investigation for the replayed run (D5 replay)."""
    from ..model import list_sessions

    root = extract_bundle(artifact)
    manifest_path = root / MANIFEST_FILENAME
    if not manifest_path.exists():
        raise ValueError("not a devtool bundle (no manifest.json): " + str(artifact))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    repro = root / REPRO_FILENAME
    if not repro.exists():
        raise ValueError("bundle has no repro.sh -- nothing to replay: " + str(artifact))
    cmd: List[str] = []
    cwd = ""
    for line in repro.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("cd "):
            parts = shlex.split(line[3:])
            cwd = parts[0] if parts else ""
        elif line.startswith("exec "):
            cmd = shlex.split(line[5:])
    if not cmd:
        raise ValueError("bundle repro.sh has no exec line")

    import os
    env = dict(os.environ)
    env["IMAGE_TOOLKIT_TELEMETRY"] = "1"
    before = time.time()
    try:
        proc = subprocess.run(
            cmd, cwd=cwd or str(Path.cwd()), env=env, capture_output=True, text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        proc = subprocess.CompletedProcess(cmd, -9, "", "replay timed out (120s)")
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=__import__("sys").stderr)

    # Link the newest telemetry session written during the replay, the same
    # way cmd_repro does for a first run.
    sessions = [s for s in list_sessions() if s.stat().st_mtime >= before]
    session_path = sessions[-1] if sessions else None

    name = "replay-" + str(manifest.get("name", "unknown")) + "-" + str(int(time.time()))
    try:
        inv = store.create_investigation(name)
    except FileExistsError:
        inv = store.open_investigation(name)
    inv.append_note(
        "replayed from bundle: exit=" + str(proc.returncode) + " cmd=" + " ".join(map(str, cmd)),
        author="tool.repro",
    )
    if session_path is not None:
        inv.link_session(str(session_path))
    return {
        "investigation": name,
        "root": str(inv.root),
        "exit_code": proc.returncode,
        "command": cmd,
        "session": str(session_path) if session_path is not None else None,
        "stderr_tail": (proc.stderr or "")[-500:],
    }


__all__ = [
    "BundleResult",
    "build_bundle",
    "extract_bundle",
    "replay_bundle",
]
