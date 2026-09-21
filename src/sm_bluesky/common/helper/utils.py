from collections.abc import Sequence


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
