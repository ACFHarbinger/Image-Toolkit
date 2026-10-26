from __future__ import annotations

from pathlib import Path

import pytest
from middleware.src.services.stitch.status import REASON, ROUTES, stitch_status


@pytest.mark.parametrize("route", sorted(ROUTES))
def test_known_route_is_not_started(route: str) -> None:
    assert stitch_status(route) == {"route": route, "started": False, "reason": REASON}


@pytest.mark.parametrize("route", ["", "stitch.canvas ", "stitch.nope", "system.convert"])
def test_unknown_route_is_an_error(route: str) -> None:
    with pytest.raises(ValueError, match="unknown stitch route"):
        stitch_status(route)


def test_status_module_does_not_name_a_pipeline() -> None:
    text = Path(stitch_status.__code__.co_filename).read_text(encoding="utf-8")
    assert "AnimeStitchPipeline" not in text
    assert ".image-toolkit" not in text
