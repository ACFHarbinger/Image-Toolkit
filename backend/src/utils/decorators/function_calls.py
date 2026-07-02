from __future__ import annotations

import functools
import logging
import time
from typing import Callable, TypeVar

_F = TypeVar("_F", bound=Callable)


def log_call(logger: logging.Logger | None = None) -> Callable[[_F], _F]:
    """Decorator that logs entry/exit and elapsed time for a function call.

    Compatible with the §5.4B trace JSON format: timings are recorded as
    ``{"stage": name, "elapsed_ms": float}`` via the supplied logger at DEBUG level.

    Usage::

        @log_call()
        def my_stage(self, ...): ...

        @log_call(logger=logging.getLogger("my_module"))
        def my_stage(self, ...): ...
    """

    def decorator(fn: _F) -> _F:
        _logger = logger or logging.getLogger(fn.__module__)

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            _logger.debug("→ %s", fn.__qualname__)
            t0 = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
                elapsed = (time.perf_counter() - t0) * 1000
                _logger.debug("← %s  %.1f ms", fn.__qualname__, elapsed)
                return result
            except Exception:
                elapsed = (time.perf_counter() - t0) * 1000
                _logger.debug("✗ %s  %.1f ms (raised)", fn.__qualname__, elapsed)
                raise

        return wrapper  # type: ignore[return-value]

    return decorator


__all__ = ["log_call"]
