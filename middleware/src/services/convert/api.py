"""Public API surface for the Convert service (Issue #881, Wave 0e W0-17).

Callers outside `middleware.src.services.convert` should import from
`middleware.src.services.convert.api` (or `middleware.src.services.convert`).
"""

from __future__ import annotations

from middleware.src.services.convert.commands import (
    BatchConvertCommand,
    BatchConvertResult,
    ConvertSingleCommand,
    ConvertSingleResult,
)
from middleware.src.services.convert.handlers import BatchConvertHandler, ConvertSingleHandler
from middleware.src.services.convert.protocols import ConvertServiceProtocol
from middleware.src.services.convert.service import ConvertService

__all__ = [
    "BatchConvertCommand",
    "BatchConvertHandler",
    "BatchConvertResult",
    "ConvertService",
    "ConvertServiceProtocol",
    "ConvertSingleCommand",
    "ConvertSingleHandler",
    "ConvertSingleResult",
]
