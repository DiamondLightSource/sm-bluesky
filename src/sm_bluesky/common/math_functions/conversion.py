from math import ceil, floor


def cal_range_num(cen: float, range: float, size: float) -> tuple[float, float, int]:
    """Calculate the start, end and the number of steps for a scan."""
    start_pos = cen - range
    end_pos = cen + range
    num = ceil(abs(range * 4.0 / size))
    return start_pos, end_pos, num


def step_size_to_step_num(start: float, end: float, step_size: float) -> int:
    """Quick conversion to step from step size.

    Parameters
    ----------
    start : float
        Starting position.
    end : float
        Ending position.
    step_size : float
        Step size.

    Returns
    -------
    int
        Number of steps.
    """
    step_range = abs(start - end)
    return floor(step_range / step_size)
