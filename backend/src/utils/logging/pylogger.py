"""Multi-GPU friendly Python logging utilities.

This module provides a specialized logger initialization that is compatible with
distributed training environments. It ensures that logs are only emitted from
the primary process (rank zero) to prevent terminal output clutter and
multiplication. It also optionally integrates with structured JSON logging if a
file path is provided.

Attributes:
    get_pylogger: Primary utility for initializing rank-zero-only loggers.

Example:
    >>> from logic.src.tracking.logging.pylogger import get_pylogger
    >>> logger = get_pylogger(__name__)
    >>> logger.info("This message only appears once on rank zero.")
"""

from __future__ import annotations

import logging
from typing import Optional

from lightning.fabric.utilities.rank_zero import rank_zero_only

from logic.src.tracking.logging.structured_logging import get_structured_logger as _get_structured


def get_pylogger(name: str = __name__, log_file: Optional[str] = None) -> logging.Logger:
    """Initializes a multi-GPU-friendly Python command line logger.

    Wraps standard logging methods with the rank_zero_only decorator to prevent
    duplicate output in distributed settings.

    Args:
        name: The name used for the logger instance. Defaults to the module name.
        log_file: Optional path to a log file. If provided, enables structured
            JSON logging to that file. Defaults to None.

    Returns:
        logging.Logger: The configured rank-zero-safe logger.
    """
    # If log_file is provided, use structured logger setup first
    logger = _get_structured(name=name, log_file=log_file) if log_file else logging.getLogger(name)

    # this ensures all logging levels get marked with the rank zero decorator
    # otherwise logs would get multiplied for each GPU process in multi-GPU setup
    logging_levels = (
        "debug",
        "info",
        "warning",
        "error",
        "exception",
        "fatal",
        "critical",
    )
    for level in logging_levels:
        setattr(logger, level, rank_zero_only(getattr(logger, level)))

    return logger
