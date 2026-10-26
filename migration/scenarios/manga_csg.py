"""Manga CSG differential: the contract payload shape vs the bridge handler
projection (E-03 / #916, #883 harness).

The legacy side is the payload shape the ``csg`` contract promises — the
field set the Phase C service API results have carried since #867. The
service side runs the actual sidecar handlers over the same seeded fake
solver results, so the comparison locks the bridge projection (tuples
normalized to lists, no field drift) against the contract. No CSG solver
runs and no image loads — the fake service answers offline.
"""

from __future__ import annotations

from middleware.src.services.csg.commands import (
    ArapDeformResult,
    ColorizeReferenceResult,
    ColorizeScribbleResult,
    TemporalPropagateResult,
)
from middleware.src.sidecar.handlers.csg import (
    handle_arap_deform,
    handle_colorize_reference,
    handle_colorize_scribble,
    handle_propagate_sequence,
)


class _FakeService:
    """Answers every CsgService method with the seeded result."""

    def colorize_scribble(self, command):
        return ColorizeScribbleResult(
            success=True,
            output_path="/tmp/csg/scribble.png",
            width=800,
            height=1200,
            elapsed_seconds=0.25,
        )

    def colorize_reference(self, command):
        return ColorizeReferenceResult(
            success=True,
            output_path="/tmp/csg/reference.png",
            width=800,
            height=1200,
            elapsed_seconds=0.4,
        )

    def arap_deform(self, command):
        return ArapDeformResult(
            success=True,
            output_path="/tmp/csg/pose.png",
            num_vertices=57,
            num_triangles=90,
            elapsed_seconds=0.5,
        )

    def propagate_sequence(self, command):
        return TemporalPropagateResult(
            success=True,
            output_paths=("/tmp/csg/f1.png", "/tmp/csg/f2.png"),
            frames_processed=2,
            elapsed_seconds=0.6,
        )


def pair(tmp: object) -> tuple[dict[str, object], dict[str, object]]:
    service = _FakeService()
    return _legacy(), {
        "colorize_scribble": handle_colorize_scribble(
            service,
            {"lineart_path": "/lineart.png", "scribble_path": "/hints.png"},
        ),
        "colorize_reference": handle_colorize_reference(
            service,
            {"lineart_path": "/lineart.png", "reference_path": "/palette.png"},
        ),
        "arap_deform": handle_arap_deform(
            service,
            {
                "image_path": "/sprite.png",
                "control_points": [[10, 20], [80, 25]],
                "target_points": [[12, 24], [95, 20]],
            },
        ),
        "propagate_sequence": handle_propagate_sequence(
            service,
            {"frame_paths": ["/f1.png", "/f2.png"]},
        ),
    }


def _legacy() -> dict[str, object]:
    return {
        "colorize_scribble": {
            "success": True,
            "output_path": "/tmp/csg/scribble.png",
            "width": 800,
            "height": 1200,
            "elapsed_seconds": 0.25,
            "error": None,
        },
        "colorize_reference": {
            "success": True,
            "output_path": "/tmp/csg/reference.png",
            "width": 800,
            "height": 1200,
            "elapsed_seconds": 0.4,
            "error": None,
        },
        "arap_deform": {
            "success": True,
            "output_path": "/tmp/csg/pose.png",
            "num_vertices": 57,
            "num_triangles": 90,
            "elapsed_seconds": 0.5,
            "error": None,
        },
        "propagate_sequence": {
            "success": True,
            "output_paths": ["/tmp/csg/f1.png", "/tmp/csg/f2.png"],
            "frames_processed": 2,
            "elapsed_seconds": 0.6,
            "error": None,
        },
    }
