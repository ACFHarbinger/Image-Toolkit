"""Path-validation decorators."""

from __future__ import annotations

import functools
import inspect
import os
from collections.abc import Callable
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


def require_path(*param_names: str) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Require each supplied, non-empty path argument to exist before calling.

    Optional path parameters may be ``None`` or an empty string. Positional,
    keyword, and defaulted arguments are resolved from the wrapped signature.
    """

    def decorator(fn: Callable[P, T]) -> Callable[P, T]:
        signature = inspect.signature(fn)

        @functools.wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            for name in param_names:
                path = bound.arguments.get(name)
                if path and not os.path.exists(path):
                    raise FileNotFoundError(f"{name}={path!r} does not exist")
            return fn(*args, **kwargs)

        return wrapper

    return decorator


__all__ = ["require_path"]
