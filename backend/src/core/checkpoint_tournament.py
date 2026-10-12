"""#747: blind pairwise ELO tournament over a run's checkpoint sample grids.

After a run finishes there is no guidance on which checkpoint to keep; the
tournament turns eyeballing folders into a measured preference signal.
The user is shown two checkpoint sample grids side by side with the ids
hidden, picks left/right/tie, and an ELO table with per-entry uncertainty
grows on the run. The outcome persists to ``tournament.json`` beside
``record.json`` — that file is the grounded-evidence contract Gate E's
guidance loop reads ("checkpoint 6 wins blind while effective rank
saturates at 9/64").

Inputs, all read-only:

- checkpoints: ``record.json`` → ``config.output_dir`` →
  ``checkpoint-epochNNNN/`` (diffusers save_pretrained dirs, the layout
  ``backend/src/models/tuning/lo_ra_tuner_v2.py`` writes and #743 walks)
  plus the final artifact from ``lora_path``;
- sample grids: ``<run_dir>/samples/step-NNNNNN.png`` (the Gate D.2
  writer's layout). When no grids exist yet the tournament cannot run —
  callers degrade with an explanation instead of guessing.

Pure: no Qt, no torch — GUI tests and Gate E consumers import freely.
"""
from __future__ import annotations

import json
import math
import random
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from backend.src.core.training_runs import read_run_record

ELO_START = 1500.0
ELO_K = 32.0
# Glicko-lite provisional deviation at zero games; margin is ±2·RD.
RD_BASE = 350.0
# Below this many total comparisons the UI must call the table provisional.
SIGNIFICANT_GAMES = 10

RESULT_A = "a"
RESULT_B = "b"
RESULT_TIE = "tie"
RESULTS = (RESULT_A, RESULT_B, RESULT_TIE)

STATE_FILE_NAME = "tournament.json"
SAMPLES_DIR_NAME = "samples"

_CHECKPOINT_DIR_RE = re.compile(r"^checkpoint-epoch(\d+)$")
_SAMPLE_STEP_RE = re.compile(r"^step-(\d+)\.png$")
_SAFE_LABEL_RE = re.compile(r"[^A-Za-z0-9_. -]+")


@dataclass
class TournamentEntry:
    """One checkpoint plus the sample grid that stands in for it."""

    key: str  # "epoch-0003" | "final" — stable across sittings
    label: str  # human-readable, revealed only after votes land
    checkpoint_path: str
    sample_path: str
    rating: float = ELO_START
    games: int = 0
    wins: int = 0
    ties: int = 0


@dataclass
class Standing:
    label: str
    key: str
    rating: float
    margin: float  # ±2·RD at the entry's game count
    games: int
    wins: int
    ties: int


@dataclass
class CheckpointInfo:
    key: str
    label: str
    path: str
    epoch: int | None  # None for the final artifact


@dataclass
class SampleGrid:
    path: str
    step: int


@dataclass
class TournamentState:
    run_id: str
    entries: dict[str, TournamentEntry] = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)
    promoted: dict | None = None


# ---------------------------------------------------------------------------
# ELO core
# ---------------------------------------------------------------------------

def expected_score(rating_a: float, rating_b: float) -> float:
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


def uncertainty_margin(games: int) -> float:
    """±2·RD with RD = RD_BASE/√(games+1) — wide when provisional."""
    return 2.0 * RD_BASE / math.sqrt(games + 1.0)


def record_result(
    state: TournamentState,
    a_key: str,
    b_key: str,
    result: str,
    *,
    ts: float | None = None,
) -> bool:
    """Score one comparison. Returns False when the pair (unordered) was
    already played — the UI must skip ahead instead of double-counting."""
    if a_key == b_key or result not in RESULTS:
        return False
    a = state.entries.get(a_key)
    b = state.entries.get(b_key)
    if a is None or b is None:
        return False
    played = {
        frozenset((h["a"], h["b"])) for h in state.history
    }
    if frozenset((a_key, b_key)) in played:
        return False

    score_a = {RESULT_A: 1.0, RESULT_TIE: 0.5, RESULT_B: 0.0}[result]
    ea = expected_score(a.rating, b.rating)
    a.rating += ELO_K * (score_a - ea)
    b.rating += ELO_K * ((1.0 - score_a) - (1.0 - ea))
    a.games += 1
    b.games += 1
    if result == RESULT_TIE:
        a.ties += 1
        b.ties += 1
    elif result == RESULT_A:
        a.wins += 1
    else:
        b.wins += 1
    state.history.append(
        {
            "a": a_key,
            "b": b_key,
            "result": result,
            "ts": ts if ts is not None else time.time(),
            "rating_a": round(a.rating, 1),
            "rating_b": round(b.rating, 1),
        }
    )
    return True


def suggest_pair(
    state: TournamentState,
    rng: random.Random | None = None,
    *,
    avoid: set[frozenset] | None = None,
) -> tuple[str, str] | None:
    """Pick the next unplayed pair: closest ratings first (informative
    games), tiebreak on fewest combined games (spread play across
    entries). *avoid* excludes pairs the user skipped this sitting.
    Returns the keys blind-side randomized when *rng* is given."""
    rng = rng or random.Random()
    keys = [k for k, e in state.entries.items() if e.sample_path]
    played = {frozenset((h["a"], h["b"])) for h in state.history}
    played |= (avoid or set())
    best: tuple[float, int, str, str] | None = None
    for i, ka in enumerate(keys):
        for kb in keys[i + 1:]:
            if frozenset((ka, kb)) in played:
                continue
            a, b = state.entries[ka], state.entries[kb]
            closeness = abs(expected_score(a.rating, b.rating) - 0.5)
            fatigue = a.games + b.games
            cand = (closeness, fatigue, ka, kb)
            if best is None or cand[:2] < best[:2]:
                best = cand
    if best is None:
        return None
    pair = [best[2], best[3]]
    rng.shuffle(pair)
    return pair[0], pair[1]


def standings(state: TournamentState) -> list[Standing]:
    rows = [
        Standing(
            label=e.label,
            key=k,
            rating=e.rating,
            margin=uncertainty_margin(e.games),
            games=e.games,
            wins=e.wins,
            ties=e.ties,
        )
        for k, e in state.entries.items()
    ]
    rows.sort(key=lambda s: (-s.rating, s.label))
    return rows


def total_games(state: TournamentState) -> int:
    """Comparisons recorded — one per history row, however many entries
    each touched."""
    return len(state.history)


def is_significant(state: TournamentState) -> bool:
    """ELO needs ~10+ comparisons before it means much (#747)."""
    return total_games(state) >= SIGNIFICANT_GAMES


# ---------------------------------------------------------------------------
# Persistence — <run_dir>/tournament.json (the Gate E evidence contract)
# ---------------------------------------------------------------------------

def state_to_dict(state: TournamentState) -> dict:
    return {
        "version": 1,
        "run_id": state.run_id,
        "entries": {k: asdict(e) for k, e in state.entries.items()},
        "history": list(state.history),
        "promoted": state.promoted,
    }


def state_from_dict(data: dict) -> TournamentState:
    entries = {
        k: TournamentEntry(**v) for k, v in (data.get("entries") or {}).items()
    }
    return TournamentState(
        run_id=str(data.get("run_id") or ""),
        entries=entries,
        history=[h for h in (data.get("history") or []) if isinstance(h, dict)],
        promoted=data.get("promoted") if isinstance(data.get("promoted"), dict) else None,
    )


def save_state(run_dir: Path | str, state: TournamentState) -> Path:
    path = Path(run_dir) / STATE_FILE_NAME
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state_to_dict(state), indent=1), encoding="utf-8")
    tmp.replace(path)
    return path


def load_state(run_dir: Path | str) -> TournamentState | None:
    path = Path(run_dir) / STATE_FILE_NAME
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return state_from_dict(data)


def attach_state(run_dir: Path | str, entries: list[TournamentEntry]) -> TournamentState:
    """Bind discovered entries to saved ratings: known keys resume where
    the last sitting left off, new checkpoints start at ELO_START, and
    history for deleted checkpoints drops out."""
    run_id = Path(run_dir).name
    record = read_run_record(run_dir)
    if record and record.get("run_id"):
        run_id = str(record["run_id"])
    old = load_state(run_dir)
    if old is None:
        return TournamentState(run_id=run_id, entries={e.key: e for e in entries})
    by_key = {e.key: e for e in entries}
    for key, entry in by_key.items():
        prev = old.entries.get(key)
        if prev is not None:
            entry.rating = prev.rating
            entry.games = prev.games
            entry.wins = prev.wins
            entry.ties = prev.ties
    alive = set(by_key)
    history = [
        h
        for h in old.history
        if h.get("a") in alive and h.get("b") in alive
    ]
    return TournamentState(
        run_id=old.run_id or run_id,
        entries=by_key,
        history=history,
        promoted=old.promoted if old.promoted and old.promoted.get("key") in alive else None,
    )


def promote(state: TournamentState, key: str, *, ts: float | None = None) -> dict:
    """Mark the winner; the record doubles as Generate-adapter provenance."""
    entry = state.entries[key]
    state.promoted = {
        "key": entry.key,
        "label": entry.label,
        "checkpoint_path": entry.checkpoint_path,
        "rating": round(entry.rating, 1),
        "margin": round(uncertainty_margin(entry.games), 1),
        "games": entry.games,
        "run_id": state.run_id,
        "ts": ts if ts is not None else time.time(),
    }
    return state.promoted


# ---------------------------------------------------------------------------
# Discovery — checkpoints from the output dir, grids from the run dir
# ---------------------------------------------------------------------------

def _has_weights(path: Path) -> bool:
    try:
        return any(p.suffix == ".safetensors" for p in path.rglob("*.safetensors"))
    except OSError:
        return False


def read_output_dir(run_dir: Path | str) -> Path | None:
    record = read_run_record(run_dir)
    if not record:
        return None
    raw = (record.get("config") or {}).get("output_dir")
    if not raw:
        raw = record.get("lora_path")
    if not raw:
        return None
    return Path(str(raw)).expanduser()


def discover_checkpoints(run_dir: Path | str) -> list[CheckpointInfo]:
    """``checkpoint-epochNNNN/`` dirs with weights plus the final artifact."""
    out_dir = read_output_dir(run_dir)
    found: list[CheckpointInfo] = []
    if out_dir is not None and out_dir.is_dir():
        try:
            children = sorted(out_dir.iterdir())
        except OSError:
            children = []
        for child in children:
            match = _CHECKPOINT_DIR_RE.match(child.name)
            if match and child.is_dir() and _has_weights(child):
                epoch = int(match.group(1))
                found.append(
                    CheckpointInfo(
                        key=f"epoch-{epoch:04d}",
                        label=f"epoch {epoch:04d}",
                        path=str(child),
                        epoch=epoch,
                    )
                )
    record = read_run_record(run_dir)
    final = ""
    if record:
        candidate = str(record.get("lora_path") or "")
        if candidate and Path(candidate).expanduser().is_file():
            final = candidate
    if not final and out_dir is not None and out_dir.is_dir():
        try:
            files = [p for p in out_dir.glob("*.safetensors") if p.is_file()]
        except OSError:
            files = []
        if files:
            final = str(max(files, key=lambda p: p.stat().st_mtime))
    if final:
        found.append(
            CheckpointInfo(key="final", label="final", path=final, epoch=None)
        )
    found.sort(key=lambda c: (c.epoch is None, c.epoch if c.epoch is not None else 0))
    return found


def discover_sample_grids(run_dir: Path | str) -> list[SampleGrid]:
    samples = Path(run_dir) / SAMPLES_DIR_NAME
    grids: list[SampleGrid] = []
    try:
        children = sorted(samples.iterdir())
    except OSError:
        return []
    for child in children:
        match = _SAMPLE_STEP_RE.match(child.name)
        if match and child.is_file():
            grids.append(SampleGrid(path=str(child), step=int(match.group(1))))
    grids.sort(key=lambda g: g.step)
    return grids


def _epoch_upper_steps(events: list[dict], n_epochs: int) -> dict[int, int]:
    """Max step per epoch, for mapping a checkpoint to a sample grid.
    Falls back to an even split of the highest seen step when the events
    carry no epoch tags (old runs, or sinks that dropped them)."""
    tagged: dict[int, int] = {}
    top = 0
    for ev in events:
        step = ev.get("step")
        if not isinstance(step, int):
            continue
        top = max(top, step)
        epoch = ev.get("epoch")
        if isinstance(epoch, int):
            tagged[epoch] = max(tagged.get(epoch, 0), step)
    if tagged and len(tagged) >= n_epochs:
        return tagged
    if top <= 0 or n_epochs <= 0:
        return tagged
    return {e: ((e + 1) * top) // n_epochs for e in range(n_epochs)}


def associate_sample(
    info: CheckpointInfo,
    grids: list[SampleGrid],
    epoch_upper: dict[int, int],
) -> SampleGrid | None:
    """The grid logged closest to (at or before) the checkpoint's last step
    — the sample a user would have eyeballed for that checkpoint."""
    if not grids:
        return None
    if info.epoch is None or info.epoch not in epoch_upper:
        return grids[-1]
    limit = epoch_upper[info.epoch]
    candidates = [g for g in grids if g.step <= limit]
    return candidates[-1] if candidates else None


def build_entries(
    run_dir: Path | str,
    *,
    events: list[dict] | None = None,
    rng: random.Random | None = None,
) -> list[TournamentEntry]:
    """Full discovery pipeline → tournament-ready entries (those with a
    grid attached; need ≥2 to run)."""
    if events is None:
        from backend.src.core.training_runs import iter_events

        events = list(iter_events(run_dir))
    checkpoints = discover_checkpoints(run_dir)
    grids = discover_sample_grids(run_dir)
    n_epochs = max((c.epoch for c in checkpoints if c.epoch is not None), default=-1) + 1
    epoch_upper = _epoch_upper_steps(events, n_epochs)
    entries: list[TournamentEntry] = []
    for info in checkpoints:
        grid = associate_sample(info, grids, epoch_upper)
        if grid is None:
            continue
        entries.append(
            TournamentEntry(
                key=info.key,
                label=info.label,
                checkpoint_path=info.path,
                sample_path=grid.path,
            )
        )
    if rng is not None:
        rng.shuffle(entries)
    return entries


def sanitize_label(text: str) -> str:
    """Pin labels come from our own epoch/final strings, but keep the
    spine's chip text safe regardless."""
    return _SAFE_LABEL_RE.sub("", text).strip() or "checkpoint"
