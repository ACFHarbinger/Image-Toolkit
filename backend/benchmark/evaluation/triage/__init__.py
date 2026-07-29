"""Optional FiftyOne (Voxel51) corpus-triage surface for the ASP benchmark.

The corpus-level half of the evaluation tooling (issue #123): a grouped dataset
with one group per test and one slice per comparator, every benchmark metric and
human judgment as a filterable sample field, defect tags, and saved views for the
triage queries this workflow actually asks.

FiftyOne is an **optional dev extra** — it pulls ~30 packages plus an embedded
MongoDB, and this is a dev-only benchmark tool, so nothing here is imported by
the inspector or the shared data layer. ``preflight.check()`` reports what's
missing with the exact command to fix it.

Division of labour with the inspector, and why: FiftyOne's App has no label
drawing (annotation is delegated to CVAT/Label Studio/Labelbox), its
``PlotlyView`` exposes only ``onClick``/``onSelected``/``onDoubleClick`` with no
relayout event so Plotly's ``drawrect`` can't round-trip, and it has no pixel
probe or live compositing slider on the media. Those are exactly the inspector's
job; this surface owns the grid, filtering, tagging and saved views.
"""

from .preflight import Preflight, check, require

__all__ = ["Preflight", "check", "require"]
