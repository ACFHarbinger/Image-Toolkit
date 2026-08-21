"""Natural-Language Root-Cause Hypothesis Generator (Track A4).

Analyzes telemetry session anomalies (orphans, overlaps, truncation) combined with
process exit codes and GDB/JVM stack traces to infer likely root causes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from ...model import Session


def _inspect_exit_code(exit_code: int) -> List[str]:
    if exit_code == 0:
        return []
    if exit_code in (134, -6):
        return ["Process aborted via SIGABRT (exit 134/abort) — typically glibc heap corruption assertion or uncaught C++ exception."]
    if exit_code in (139, -11):
        return ["Process terminated via SIGSEGV (exit 139/segmentation fault) — invalid pointer dereference or use-after-free."]
    return [f"Process exited with non-zero error code {exit_code}."]


def _inspect_session(session: "Session") -> List[str]:
    out: List[str] = []
    if session.truncated_final_line:
        out.append(
            "Process died mid-telemetry write: The final JSONL event was truncated, indicating sudden termination (SIGSEGV/SIGABRT) without clean Python atexit cleanup."
        )

    orphans = session.orphaned_spans()
    if orphans:
        orphan_categories = {o.category for o in orphans}
        orphan_names = {o.name for o in orphans}
        out.append(
            f"Active in-flight operations at termination ({len(orphans)} orphaned): Subsystems involved: {', '.join(sorted(orphan_categories))} ({', '.join(sorted(orphan_names)[:4])})."
        )
        if "downloader" in orphan_categories or any("download" in n for n in orphan_names):
            out.append("Network/Downloader concurrency pattern: Download worker was actively processing HTTP/TLS requests during the fault. Verify socket notifier and thread safety.")
        if "scanner" in orphan_categories and "extractor" in orphan_categories:
            out.append("Multi-worker pipeline contention: Gallery directory scanner and video extractor were running simultaneously.")

    overlaps = session.overlapping_windows()
    if overlaps:
        out.append(
            f"Thread collision detected ({len(overlaps)} overlapping worker windows): Concurrent execution of background worker loops may have caused race conditions or un-synchronized Qt event loop interactions."
        )
    return out


def _inspect_gdb(gdb_trace: str) -> List[str]:
    if not gdb_trace:
        return []
    out: List[str] = []
    trace_lower = gdb_trace.lower()
    if "deleteorphaned" in trace_lower:
        out.append("Native Qt crash signature: Corrupted connection list in QObjectPrivate::ConnectionData::deleteOrphaned.")
    elif "qsocketnotifier" in trace_lower or "invalid socket" in trace_lower:
        out.append("Qt socket notifier cross-thread violation: Socket notifiers were accessed or freed from a non-owner thread.")
    elif "corrupted size vs. prev_size" in trace_lower or "malloc" in trace_lower:
        out.append("Glibc memory corruption: Heap chunk header corruption during malloc/free consolidation.")
    elif "qobject::connect" in trace_lower:
        out.append("Native Qt connection crash: QObject::connect executed on corrupted receiver/sender object pointers.")
    return out


def generate_hypothesis(
    session: Optional["Session"],
    exit_code: int = 0,
    gdb_trace: str = "",
) -> str:
    """Generate a structured, natural-language hypothesis explaining a run's findings."""
    if exit_code == 0 and (session is None or (not session.truncated_final_line and not session.orphaned_spans() and not session.overlapping_windows())):
        return "Clean execution: Process exited with code 0 without truncated events, orphaned spans, or worker collisions."

    hypotheses: List[str] = []
    hypotheses.extend(_inspect_exit_code(exit_code))
    if session is not None:
        hypotheses.extend(_inspect_session(session))
    hypotheses.extend(_inspect_gdb(gdb_trace))

    if not hypotheses:
        return "No specific anomaly pattern identified. Review the raw telemetry and stack trace for further diagnostic cues."

    return "\n".join(f"- {h}" for h in hypotheses)
