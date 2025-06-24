from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, cast

from blueapi.core import MsgGenerator

TCallable = TypeVar("TCallable", bound=Callable[..., MsgGenerator])


def add_default_metadata(
    func: TCallable, extra_metadata: dict[str, Any] | None = None
) -> TCallable:
    """
    Decorator to add or update default metadata in the 'md' keyword argument.

    If 'md' is not provided, it will be set to extra_metadata.
    If 'md' is provided and not None, it will be updated with extra_metadata.
    If 'md' is provided and is None, it will be set to extra_metadata.
    """

    @wraps(func)
    def inner(
        *args,
        **kwargs,
    ) -> MsgGenerator:
        md = kwargs.get("md")
        if extra_metadata:
            if md is None:
                kwargs["md"] = extra_metadata
            elif isinstance(md, dict):
                # Avoid mutating the original dict
                merged = dict(md)
                merged.update(extra_metadata)
                kwargs["md"] = merged
            else:
                kwargs["md"] = extra_metadata
        elif md is None:
            kwargs["md"] = {}
        return func(*args, **kwargs)

    return cast(TCallable, inner)
