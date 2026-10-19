import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import List, Literal, Optional


@dataclass
class StageEntry:
    stage_index: int
    stage_name: str
    started_at: str
    duration_ms: float
    status: Literal["ok", "error", "skipped"]
    error: Optional[str] = None

@dataclass
class PipelineTrace:
    run_id: str
    started_at: str
    stages: List[StageEntry] = field(default_factory=list)

    def __post_init__(self):
        self._stage_starts = {}

    def begin_stage(self, index: int, name: str) -> None:
        now_dt = datetime.utcnow()
        self._stage_starts[index] = now_dt
        now_str = now_dt.isoformat() + "Z"
        entry = StageEntry(
            stage_index=index,
            stage_name=name,
            started_at=now_str,
            duration_ms=0.0,
            status="skipped", # Will be updated
            error=None
        )
        self.stages.append(entry)

    def end_stage(self, index: int, status: Literal["ok", "error", "skipped"], error: Optional[str] = None) -> None:
        # Find the stage
        for entry in reversed(self.stages):
            if entry.stage_index == index:
                now = datetime.utcnow()
                start_time = self._stage_starts.get(index)
                delta = (now - start_time).total_seconds() * 1000 if start_time else 0.0

                entry.duration_ms = delta
                entry.status = status
                entry.error = error
                break

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    def save(self, path: str) -> None:
        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())
