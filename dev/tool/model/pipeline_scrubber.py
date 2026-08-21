"""4D Pipeline Execution Time Scrubbing model (Issue #418 / D44 / D60 / D61).

Candidate B Spike: Animates and scrubs multi-stage telemetry dataflows and
frame transformations across pipeline stages (ASP stitching, HIE processing,
batch extraction) over a continuous microsecond timeline.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PipelineStageEvent:
    """Telemetry data for a single stage execution within a pipeline run."""

    id: str
    stage_name: str
    start_ms: float
    end_ms: float
    status: str = "completed"  # "pending" | "running" | "completed" | "failed" | "fallback"
    input_artifacts: List[str] = field(default_factory=list)
    output_artifacts: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        return max(0.0, self.end_ms - self.start_ms)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PipelineStageEvent":
        return cls(
            id=data["id"],
            stage_name=data["stage_name"],
            start_ms=float(data["start_ms"]),
            end_ms=float(data["end_ms"]),
            status=data.get("status", "completed"),
            input_artifacts=list(data.get("input_artifacts", [])),
            output_artifacts=list(data.get("output_artifacts", [])),
            metrics={k: float(v) for k, v in data.get("metrics", {}).items()},
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class StageActiveState:
    """State of a stage at a specific scrub timestamp."""

    stage_id: str
    stage_name: str
    status: str  # "pending" | "running" | "completed" | "failed"
    progress: float  # 0.0 to 1.0
    active_duration_ms: float


@dataclass
class PipelineScrubSession:
    """A scrubbable multi-stage pipeline execution session."""

    session_id: str
    pipeline_name: str
    stages: List[PipelineStageEvent] = field(default_factory=list)
    start_time_ms: float = 0.0
    end_time_ms: float = 0.0

    def add_stage(self, stage: PipelineStageEvent) -> None:
        self.stages.append(stage)
        if not self.stages or stage.start_ms < self.start_time_ms:
            self.start_time_ms = stage.start_ms
        if stage.end_ms > self.end_time_ms:
            self.end_time_ms = stage.end_ms

    @property
    def total_duration_ms(self) -> float:
        return max(0.0, self.end_time_ms - self.start_time_ms)

    def evaluate_at(self, t_ms: float) -> Dict[str, Any]:
        """Compute the snapshot state of all pipeline stages at time `t_ms`."""
        stage_states: List[StageActiveState] = []
        active_stage_ids: List[str] = []
        completed_stage_ids: List[str] = []

        for stage in self.stages:
            if t_ms < stage.start_ms:
                status = "pending"
                progress = 0.0
                active_dur = 0.0
            elif t_ms >= stage.end_ms:
                status = stage.status
                progress = 1.0
                active_dur = stage.duration_ms
                completed_stage_ids.append(stage.id)
            else:
                status = "running"
                dur = stage.duration_ms
                progress = (t_ms - stage.start_ms) / max(dur, 0.001)
                active_dur = t_ms - stage.start_ms
                active_stage_ids.append(stage.id)

            stage_states.append(
                StageActiveState(
                    stage_id=stage.id,
                    stage_name=stage.stage_name,
                    status=status,
                    progress=min(1.0, max(0.0, progress)),
                    active_duration_ms=active_dur,
                )
            )

        return {
            "timestamp_ms": t_ms,
            "relative_progress": (
                (t_ms - self.start_time_ms) / max(self.total_duration_ms, 0.001)
                if self.total_duration_ms > 0
                else 1.0
            ),
            "stages": [asdict(s) for s in stage_states],
            "active_stage_ids": active_stage_ids,
            "completed_stage_ids": completed_stage_ids,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "pipeline_name": self.pipeline_name,
            "start_time_ms": self.start_time_ms,
            "end_time_ms": self.end_time_ms,
            "stages": [s.to_dict() for s in self.stages],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PipelineScrubSession":
        session = cls(
            session_id=data["session_id"],
            pipeline_name=data["pipeline_name"],
            start_time_ms=float(data.get("start_time_ms", 0.0)),
            end_time_ms=float(data.get("end_time_ms", 0.0)),
        )
        for s in data.get("stages", []):
            session.add_stage(PipelineStageEvent.from_dict(s))
        return session
