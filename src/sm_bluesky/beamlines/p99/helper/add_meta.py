from collections.abc import Callable
from functools import wraps
from typing import TypeVar, cast

from bluesky import preprocessors as bpp

TCallable = TypeVar("TCallable", bound=Callable)


P99_DEFAULT_METADATA = {"energy": 2, "detector_dist": 100}


def add_default_metadata(funcs: TCallable) -> TCallable:
    @wraps(funcs)
    def inner(
        *args,
        **kwargs,
    ):
        yield from bpp.subs_wrapper(
            funcs(*args, **kwargs),
            P99_DEFAULT_METADATA,
        )

    return cast(TCallable, inner)
