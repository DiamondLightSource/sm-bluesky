from collections.abc import Callable
from functools import wraps
from typing import TypeVar, cast

from blueapi.core import MsgGenerator

TCallable = TypeVar("TCallable", bound=Callable[..., MsgGenerator])


def add_default_metadata(
    funcs: TCallable, extra_metadata: dict | None = None
) -> TCallable:
    @wraps(funcs)
    def inner(
        *args,
        **kwargs,
    ) -> MsgGenerator:
        if "md" in kwargs:
            kwargs["md"].update(extra_metadata)
        else:
            kwargs["md"] = extra_metadata
        yield from (funcs(*args, **kwargs))

    return cast(TCallable, inner)
