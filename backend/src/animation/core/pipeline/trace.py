import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Literal, Optional
from datetime import datetime

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

    def begin_stage(self, index: int, name: str) -> None:
        # We store the start time but we don't calculate duration until end_stage
        # So we can keep a temporary record of start times if needed, or simply
        # append a StageEntry with dummy duration/status that will be updated.
        now = datetime.utcnow().isoformat() + "Z"
        entry = StageEntry(
            stage_index=index,
            stage_name=name,
            started_at=now,
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
                # Parse started_at
                try:
                    start_time = datetime.fromisoformat(entry.started_at.replace("Z", ""))
                    delta = (now - start_time).total_seconds() * 1000
                except ValueError:
                    delta = 0.0

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
