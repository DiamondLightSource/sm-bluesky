import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, cast, get_type_hints

from bluesky.utils import MsgGenerator

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


def add_extra_names_to_meta(
    md: dict[str, Any], key: str, names: list[str]
) -> dict[str, Any]:
    if key in md:
        md[key] = md[key] + names
        return md
    md[key] = names
    return md


def auto_type_cast(func: Callable) -> Callable:
    """
    Casts positional byte arguments to hinted types.
    Skips 'self' and handles empty strings gracefully.
    """

    @wraps(func)
    def wrapper(*args) -> Callable:
        sig = inspect.signature(func)
        hints = get_type_hints(func)

        bound_args = sig.bind(*args)
        bound_args.apply_defaults()

        for name, value in bound_args.arguments.items():
            if isinstance(value, bytes) and name in hints:
                target_type = hints[name]
                try:
                    str_val = value.decode("utf-8")
                    if target_type in (int, float, str):
                        bound_args.arguments[name] = target_type(str_val)
                except (ValueError, UnicodeDecodeError) as e:
                    raise TypeError(f"Argument '{name}' casting failed: {e}") from e

        return func(*bound_args.args)

    return wrapper
