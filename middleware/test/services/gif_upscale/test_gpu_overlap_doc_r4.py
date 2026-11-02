"""R4 (#1173): the speed-ideas note must describe the overlap that actually runs.

The copy/compute module is gone. The live overlap is the decode thread, one
worker per device, and the writer thread. A correction has to sit next to the
older sentence that said otherwise.
"""

from __future__ import annotations

from pathlib import Path

_DOC = (
    Path(__file__).resolve().parents[4] / ".agent" / "reports" / "team" / "gif_resample_speed_ideas_2026-10-30.md"
)


def _implemented_later(text: str) -> str:
    start = text.index("#### Implemented later (B3, B4, D1)")
    end = text.index("### 5.7", start)
    return text[start:end]


def test_speed_ideas_name_the_live_overlap() -> None:
    section = _implemented_later(_DOC.read_text(encoding="utf-8"))
    assert "decode thread" in section
    assert "one worker per device" in section
    assert "writer thread" in section
    assert "Correction (2026-11-02)" in section
    assert "run_device_pipeline" in section
    assert "removed" in section.lower()
