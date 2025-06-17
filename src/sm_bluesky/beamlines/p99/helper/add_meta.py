from collections.abc import Callable
from functools import wraps
from typing import TypeVar, cast

from blueapi.core import MsgGenerator

TCallable = TypeVar("TCallable", bound=Callable)


P99_DEFAULT_METADATA = {"energy": 1.8, "detector_dist": 88}


def add_default_metadata(funcs: TCallable) -> TCallable:
    @wraps(funcs)
    def inner(
        *args,
        **kwargs,
    ) -> MsgGenerator:
        if "md" in kwargs:
            kwargs["md"].update(P99_DEFAULT_METADATA)
        else:
            kwargs["md"] = P99_DEFAULT_METADATA
        yield from (funcs(*args, **kwargs))

    return cast(TCallable, inner)
