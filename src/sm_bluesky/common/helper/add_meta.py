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
                kwargs["md"] = {**md, **extra_metadata}
            else:
                raise ValueError("md is reserved for meta data.")
        elif md is None:
            kwargs["md"] = {}
        return func(*args, **kwargs)

    return cast(TCallable, inner)


def add_extra_names_to_meta(md: dict, key: str, names: list[str]):
    if key in md:
        md[key] = md[key] + names
        return md
    md[key] = names
    return md
