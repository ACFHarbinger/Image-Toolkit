"""Run-provenance capture for ComfyUI prompts (#737).

`RunTracker` is a pure diffing state machine: it is fed `/queue` and
`/history` snapshots (the shapes ComfyUI's HTTP API returns) and turns
them into bounded run records carrying the executed API-format graph,
its outputs, and a terminal status. It performs no I/O, so the manager
owns the polling thread and every parsing rule here stays unit-testable.

Decoupling rule from the DL rebuild: capture happens from the HTTP API
alone and never depends on a browser view — external-browser-driven
ComfyUI sessions produce fully captured, reviewable runs.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field, replace
from typing import Any

from backend.src.constants.comfy import RunStatus

# History beyond the baseline window is marked seen without records, so
# attaching to a long-running server cannot flood the Runs destination.
BASELINE_RECORD_LIMIT = 32
MAX_RUN_RECORDS = 200
MAX_SEEN_IDS = 4096
# A queued/running id absent from both /queue and /history for this many
# consecutive polls was cancelled without ever reaching history.
VANISH_POLLS = 2

# Queue items are [number, prompt_id, prompt, extra_data, outputs_to_execute]
# (index 5, the sensitive payload, is stripped server-side).
_QUEUE_ITEM_ID = 1
_QUEUE_ITEM_PROMPT = 2
_QUEUE_ITEM_EXTRA = 3


@dataclass(frozen=True)
class OutputRef:
    """One output file the server produced for a node."""

    node_id: str
    kind: str  # "images" / "gifs" / "audio" / ...
    filename: str
    subfolder: str = ""
    type: str = "output"

    def view_url(self, server_url: str) -> str:
        from urllib.parse import quote

        return (
            f"{server_url}/view?filename={quote(self.filename)}"
            f"&subfolder={quote(self.subfolder)}&type={quote(self.type)}"
        )


@dataclass(frozen=True)
class ComfyRunRecord:
    prompt_id: str
    status: RunStatus
    workflow: dict | None = None  # executed API-format prompt graph
    client_id: str | None = None
    outputs: tuple[OutputRef, ...] = ()
    execution_time: float | None = None
    partial: bool = False  # provenance was incomplete; do not trust silently
    source: str = "history"  # "submitted" | "queue" | "history"
    first_seen: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)


def _record_updates(old: ComfyRunRecord, **changes: Any) -> ComfyRunRecord:
    merged = {**changes, "last_updated": time.time()}
    known = {f for f in old.__dataclass_fields__}
    return replace(old, **{k: v for k, v in merged.items() if k in known})


def _queue_item_graph(item: Any) -> dict | None:
    if isinstance(item, (list, tuple)) and len(item) > _QUEUE_ITEM_PROMPT:
        graph = item[_QUEUE_ITEM_PROMPT]
        return graph if isinstance(graph, dict) else None
    return None


def _queue_item_client_id(item: Any) -> str | None:
    if isinstance(item, (list, tuple)) and len(item) > _QUEUE_ITEM_EXTRA:
        extra = item[_QUEUE_ITEM_EXTRA]
        if isinstance(extra, dict):
            value = extra.get("client_id")
            return value if isinstance(value, str) else None
    return None


def _parse_outputs(history_entry: Any) -> tuple[OutputRef, ...]:
    outputs: list[OutputRef] = []
    entry_outputs = history_entry.get("outputs") if isinstance(history_entry, dict) else None
    if not isinstance(entry_outputs, dict):
        return ()
    for node_id, node_outputs in entry_outputs.items():
        if not isinstance(node_outputs, dict):
            continue
        for kind, items in node_outputs.items():
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict) or not isinstance(item.get("filename"), str):
                    continue
                subfolder = item.get("subfolder")
                out_type = item.get("type")
                outputs.append(
                    OutputRef(
                        node_id=str(node_id),
                        kind=str(kind),
                        filename=item["filename"],
                        subfolder=subfolder if isinstance(subfolder, str) else "",
                        type=out_type if isinstance(out_type, str) else "output",
                    )
                )
    return tuple(outputs)


def _parse_terminal_status(history_entry: Any) -> tuple[RunStatus, bool]:
    """Map a history entry to its terminal status and partial flag.

    ComfyUI's ExecutionStatus is {"status_str": success|error,
    "completed": bool, "messages": [...]}; older entries may lack status
    entirely. History only holds finished prompts, so an absent status
    still means terminal — but partial.
    """
    status = history_entry.get("status") if isinstance(history_entry, dict) else None
    if not isinstance(status, dict):
        return RunStatus.COMPLETED, True
    partial = not isinstance(status.get("completed"), bool)
    messages = status.get("messages")
    if isinstance(messages, list) and any(
        isinstance(m, (list, tuple)) and len(m) > 0 and m[0] == "execution_interrupted"
        for m in messages
    ):
        return RunStatus.INTERRUPTED, partial
    if status.get("status_str") == "error":
        return RunStatus.FAILED, partial
    return RunStatus.COMPLETED, partial


class RunTracker:
    """Diffs /queue and /history snapshots into run records.

    Thread-safety: callers hold the manager's provenance lock (the
    manager serializes polls and submissions); the tracker itself has no
    internal locking.
    """

    def __init__(self, record_limit: int = MAX_RUN_RECORDS) -> None:
        self._records: dict[str, ComfyRunRecord] = {}
        self._order: deque[str] = deque()
        self._record_limit = record_limit
        self._seen: set[str] = set()
        self._seen_order: deque[str] = deque()
        self._vanishing: dict[str, int] = {}
        self._listeners: list = []
        self._has_baseline = False

    # -- observation API ---------------------------------------------------

    def subscribe(self, listener) -> None:
        """Listener is invoked on every record create/update, on the
        caller's thread — GUI consumers must marshal via queued signals."""
        self._listeners.append(listener)

    def get(self, prompt_id: str) -> ComfyRunRecord | None:
        return self._records.get(prompt_id)

    def snapshot(self) -> tuple[ComfyRunRecord, ...]:
        return tuple(self._records[p_id] for p_id in self._order if p_id in self._records)

    def record_submitted(self, prompt_id: str, workflow: dict, client_id: str | None) -> None:
        """Optimistic record from our own /prompt submission."""
        if prompt_id in self._records:
            self._update(
                prompt_id,
                _record_updates(self._records[prompt_id], workflow=workflow, client_id=client_id),
            )
            return
        self._create(
            ComfyRunRecord(
                prompt_id=prompt_id,
                status=RunStatus.PENDING,
                workflow=workflow,
                client_id=client_id,
                source="submitted",
            )
        )

    def baseline_history(self, history: Any) -> None:
        """First history snapshot: emit records for the newest entries and
        mark the rest seen, so resuming never re-emits old runs."""
        self._has_baseline = True
        if not isinstance(history, dict):
            return
        ordered = sorted(
            history.items(),
            key=lambda kv: _queue_number(kv[1]),
            reverse=True,
        )
        for prompt_id, _entry in ordered:
            self._mark_seen(prompt_id)
        for prompt_id, entry in ordered[:BASELINE_RECORD_LIMIT]:
            self._apply_history_entry(prompt_id, entry)

    def observe_queue(self, queue: Any) -> None:
        if not isinstance(queue, dict):
            return
        running = {
            item_id: item for item_id, item in _iter_queue_items(queue.get("queue_running"))
        }
        pending = {
            item_id: item for item_id, item in _iter_queue_items(queue.get("queue_pending"))
        }
        active: set[str] = set()
        observations = [
            *((p, item, RunStatus.RUNNING) for p, item in running.items()),
            *((p, item, RunStatus.PENDING) for p, item in pending.items()),
        ]
        for prompt_id, item, status in observations:
            active.add(prompt_id)
            self._mark_seen(prompt_id)
            record = self._records.get(prompt_id)
            graph = _queue_item_graph(item)
            client_id = _queue_item_client_id(item)
            if record is None:
                self._create(
                    ComfyRunRecord(
                        prompt_id=prompt_id,
                        status=status,
                        workflow=graph,
                        client_id=client_id,
                        partial=graph is None,
                        source="queue",
                    )
                )
            elif record.status not in (
                RunStatus.COMPLETED,
                RunStatus.FAILED,
                RunStatus.INTERRUPTED,
            ):
                changes: dict[str, Any] = {"status": status}
                if graph is not None and record.workflow is None:
                    changes["workflow"] = graph
                if client_id is not None and record.client_id is None:
                    changes["client_id"] = client_id
                self._update(prompt_id, _record_updates(record, **changes))
        self._mark_vanished(active)

    def observe_history(self, history: Any) -> None:
        if not isinstance(history, dict):
            return
        for prompt_id, entry in history.items():
            if prompt_id in self._records:
                self._apply_history_entry(prompt_id, entry)
            elif prompt_id not in self._seen:
                # Seen-without-record ids (baselined away) never come back;
                # unknown ids are captured even if we first see them here,
                # already finished (e.g. external-browser work).
                self._mark_seen(prompt_id)
                self._apply_history_entry(prompt_id, entry)

    def observe_snapshot(self, queue: Any, history: Any, *, first: bool) -> None:
        """One poll cycle: queue first (in-flight state), then history."""
        self.observe_queue(queue)
        if first and not self._has_baseline:
            self.baseline_history(history)
        else:
            self.observe_history(history)

    # -- internals ----------------------------------------------------------

    def _apply_history_entry(self, prompt_id: str, entry: Any) -> None:
        status, partial = _parse_terminal_status(entry)
        outputs = _parse_outputs(entry)
        graph = _queue_item_graph(
            entry.get("prompt") if isinstance(entry, dict) else None
        )
        client_id = None
        if isinstance(entry, dict):
            client_id = _queue_item_client_id(entry.get("prompt"))
        record = self._records.get(prompt_id)
        if record is None:
            self._create(
                ComfyRunRecord(
                    prompt_id=prompt_id,
                    status=status,
                    workflow=graph,
                    client_id=client_id,
                    outputs=outputs,
                    partial=partial or graph is None,
                    source="history",
                )
            )
            return
        if record.status not in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.INTERRUPTED):
            changes: dict[str, Any] = {
                "status": status,
                "outputs": outputs,
                "partial": record.partial or partial,
                "source": record.source if record.source == "submitted" else "history",
            }
            if graph is not None:
                changes["workflow"] = graph
            self._update(prompt_id, _record_updates(record, **changes))
        self._vanishing.pop(prompt_id, None)

    def _mark_vanished(self, active: set[str]) -> None:
        """Ids that left the queue without ever reaching history were
        cancelled (or the server discarded them): close them out as
        partial, not stuck in Running forever."""
        for prompt_id in list(self._vanishing):
            if prompt_id in active:
                continue
            record = self._records.get(prompt_id)
            if record is None or record.status in (
                RunStatus.COMPLETED,
                RunStatus.FAILED,
                RunStatus.INTERRUPTED,
            ):
                self._vanishing.pop(prompt_id, None)
                continue
            self._vanishing[prompt_id] += 1
            if self._vanishing[prompt_id] >= VANISH_POLLS:
                self._vanishing.pop(prompt_id, None)
                self._update(
                    prompt_id,
                    _record_updates(record, status=RunStatus.INTERRUPTED, partial=True),
                )
        for prompt_id, record in list(self._records.items()):
            if (
                prompt_id not in active
                and prompt_id not in self._vanishing
                and record.status in (RunStatus.PENDING, RunStatus.RUNNING)
            ):
                self._vanishing[prompt_id] = 1

    def _mark_seen(self, prompt_id: str) -> None:
        if prompt_id in self._seen:
            return
        self._seen.add(prompt_id)
        self._seen_order.append(prompt_id)
        while len(self._seen_order) > MAX_SEEN_IDS:
            self._seen.discard(self._seen_order.popleft())

    def _create(self, record: ComfyRunRecord) -> None:
        self._records[record.prompt_id] = record
        self._order.append(record.prompt_id)
        while len(self._order) > self._record_limit:
            oldest = self._order.popleft()
            self._records.pop(oldest, None)
        self._notify(record)

    def _update(self, prompt_id: str, record: ComfyRunRecord) -> None:
        self._records[prompt_id] = record
        self._notify(record)

    def _notify(self, record: ComfyRunRecord) -> None:
        for listener in tuple(self._listeners):
            listener(record)


def _iter_queue_items(items: Any):
    if not isinstance(items, list):
        return
    for item in items:
        if not isinstance(item, (list, tuple)) or len(item) <= _QUEUE_ITEM_ID:
            continue
        prompt_id = item[_QUEUE_ITEM_ID]
        if isinstance(prompt_id, str):
            yield prompt_id, item


def _queue_number(history_entry: Any) -> int:
    if isinstance(history_entry, dict):
        prompt = history_entry.get("prompt")
        if isinstance(prompt, (list, tuple)) and prompt and isinstance(prompt[0], int):
            return prompt[0]
    return -1
