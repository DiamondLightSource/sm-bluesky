from collections.abc import Mapping, Sequence
from typing import Any


def unique_objs(objs: Sequence) -> list:
    """Return unique objects while preserving their original order.

    Useful when combining user-provided objects with additional required
    objects where duplicates should be removed without making the resulting
    order non-deterministic.

    Args:
        objs: Sequence of hashable objects.

    Returns:
        A list containing each object at most once, in the order of its
        first occurrence.
    """
    return list(dict.fromkeys(objs))


def deep_update(original: dict[str, Any], updates: Mapping[str, Any]) -> None:
    """Recursively update a dictionary with values from another mapping.

    Nested mappings are merged recursively rather than replaced, while
    non-mapping values replace any existing value for the same key.

    Args:
        original: Dictionary to update in place.
        updates: Mapping containing the values to merge into ``original``.
    """
    for key, value in updates.items():
        if (
            key in original
            and isinstance(original[key], dict)
            and isinstance(value, Mapping)
        ):
            deep_update(original[key], value)
        else:
            original[key] = value
