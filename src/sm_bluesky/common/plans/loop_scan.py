import math
from collections.abc import Sequence
from typing import Any

import bluesky.plans as bp
import numpy as np
from bluesky.protocols import HasName, Movable, Readable
from bluesky.utils import CustomPlanMetadata, MsgGenerator, get_hinted_fields, plan


def _generate_segment(
    start: float,
    stop: float,
    step_size: float,
) -> list[float]:
    if step_size == 0:
        raise ValueError(f"step_size must not be zero, got {step_size}")
    if start == stop:
        return [float(start)]

    steps = math.ceil(abs((stop - start) / step_size))
    return np.linspace(start, stop, steps + 1).tolist()


def _generate_loop_positions(
    start: float | Sequence[float],
    stop: float | Sequence[float],
    step_size: float | Sequence[float],
    mirror: bool = True,
) -> list[float]:
    starts = [float(start)] if isinstance(start, int | float) else list(start)
    stops = [float(stop)] if isinstance(stop, int | float) else list(stop)
    if not starts or len(starts) != len(stops):
        raise ValueError(
            "start and stop must not be empty and have the same length, "
            f"got {len(starts)} and {len(stops)}"
        )

    step_sizes = (
        [float(step_size)] * len(starts)
        if isinstance(step_size, int | float)
        else list(step_size)
    )
    if len(step_sizes) != len(starts):
        raise ValueError(
            "step_size must be a single value or match the number of regions "
            f"({len(starts)}), got {len(step_sizes)}"
        )

    positions: list[float] = []
    for seg_start, seg_stop, seg_step in zip(starts, stops, step_sizes, strict=True):
        segment = _generate_segment(seg_start, seg_stop, seg_step)
        if positions and math.isclose(
            positions[-1], segment[0], rel_tol=1e-9, abs_tol=1e-12
        ):
            segment = segment[1:]
        positions.extend(segment)

    if mirror:
        positions.extend(reversed(positions[:-1]))
    return positions


@plan
def loop_step_scan(
    detectors: Sequence[Readable],
    movable: Movable[float],
    start: float | Sequence[float],
    stop: float | Sequence[float],
    step_size: float | Sequence[float],
    mirror: bool = True,
    md: CustomPlanMetadata | None = None,
) -> MsgGenerator:
    """Perform a loop step scan within a single run.

    Steps ``movable`` from ``start`` to ``stop`` by ``step_size`` while reading
    ``detectors`` at each position. ``start``, ``stop``, and ``step_size`` may
    be single floats for one region or sequences of equal length to define
    multiple regions with different step sizes (a scalar ``step_size`` is
    applied to all regions). Shared boundaries between consecutive regions are
    visited once.

    When ``mirror`` is True (default), the scan symmetrically returns along the
    same positions back to the start. Set ``mirror=False`` to define
    forward and return regions (e.g. multi-segment hysteresis loops).

    Parameters
    ----------
    detectors : Sequence[Readable]
        Readable devices (e.g. detectors) to trigger and read at each step.
    movable : Movable[float]
        Movable device to step across the scan positions.
    start : float | Sequence[float]
        Starting position, or sequence of region start positions.
    stop : float | Sequence[float]
        Turnaround/ending position, or sequence of region stop positions.
    step_size : float | Sequence[float]
        Non-zero step increment, or sequence of step increments per region.
    mirror : bool, optional
        If True (default), symmetrically step back along the forward positions
        to return to the start. If False, scan only the specified regions.
    md : CustomPlanMetadata | None, optional
        Additional metadata to include in the Bluesky run start document.

    Returns
    -------
    MsgGenerator
        A Bluesky generator executing the loop scan in a single run.
    """
    movable_name = movable.name if isinstance(movable, HasName) else None
    if movable_name is not None:
        detectors = [det for det in detectors if det.name != movable_name]
    positions = _generate_loop_positions(start, stop, step_size, mirror=mirror)
    _md: dict[str, Any] = {
        "plan_name": "loop_step_scan",
        "plan_args": {
            "detectors": [repr(det) for det in detectors],
            "movable": repr(movable),
            "start": start,
            "stop": stop,
            "step_size": step_size,
            "mirror": mirror,
        },
        "plan_pattern_args": {
            "movable": repr(movable),
            "positions": positions,
        },
        **(md or {}),
    }
    if movable_name is not None and not get_hinted_fields(movable):
        _md["hints"] = {
            "dimensions": [([movable_name], "primary")],
            **(_md.get("hints") or {}),
        }
    scan_args: tuple[Any, ...] = (movable, positions)
    return (yield from bp.list_scan(detectors, *scan_args, md=_md))
