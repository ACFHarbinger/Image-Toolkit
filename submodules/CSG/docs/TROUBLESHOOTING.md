# Troubleshooting

## `uv` cannot find Python

Install Python 3.11+ through `uv python install 3.11`, then rerun
`uv sync --all-packages --all-extras --dev`.

## Qt fails without a display

For tests and smoke checks use `QT_QPA_PLATFORM=offscreen`. The interactive
application requires a working Linux desktop session.

## A solver times out or crashes

Built-in native jobs are isolated and should return an actionable error without
terminating the host. Local metadata-only diagnostics are under
`${XDG_STATE_HOME:-~/.local/state}/cel-shaded-generator/diagnostics.jsonl` and
rotate after seven days or 20 MiB. They exclude artwork pixels and request
filenames. Users may disable diagnostics and configure the five-minute cap.

## Image-Toolkit imports fail

Do not add Image-Toolkit to `PYTHONPATH`; this repository is standalone. Install
or sync both workspace packages normally.

Still stuck? Open a GitHub issue with the operation name, array dimensions,
broad hardware class, and sanitized diagnostic outcome. Do not attach private
artwork unless you intentionally choose to share it.
