"""Sidecar handlers for the logging and metadata windows (#919)."""

from __future__ import annotations

from typing import Any

from middleware.src.services.desk.logs import read_log
from middleware.src.services.desk.metadata import describe_file


def handle_logs_read(params: dict[str, Any]) -> dict[str, Any]:
    return read_log(str(params["path"]), int(params["limit"]))


def handle_metadata_describe(params: dict[str, Any]) -> dict[str, Any]:
    return describe_file(str(params["path"]))
