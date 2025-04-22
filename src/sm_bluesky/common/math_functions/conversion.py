from math import ceil, floor


def cal_range_num(cen, range, size) -> tuple[float, float, int]:
    """Calculate the start, end and the number of step for scan."""
    start_pos = cen - range
    end_pos = cen + range
    num = ceil(abs(range * 4.0 / size))
    return start_pos, end_pos, num


def step_size_to_step_num(start: float, end: float, step_size: float):
    """Quick conversion to step from step size

    Parameters
    ----------
    start : float
        starting position
    end: float
        ending position
    step_size: float
        step size

    Returns
    -------
        Number of steps : int

    """
    step_range = abs(start - end)
    return floor(step_range / step_size)
