from collections.abc import Sequence
from math import floor, sqrt
from typing import Any, TypedDict

import bluesky.plan_stubs as bps
import bluesky.plans as bp
from bluesky.preprocessors import finalize_wrapper
from bluesky.protocols import Readable
from bluesky.utils import MsgGenerator, plan
from dodal.plan_stubs.data_session import attach_data_session_metadata_decorator
from ophyd_async.epics.adcore import AreaDetector, SingleTriggerDetector
from ophyd_async.epics.motor import Motor

from sm_bluesky.common.math_functions import step_size_to_step_num
from sm_bluesky.common.plan_stubs import (
    check_within_limit,
    get_motor_positions,
    get_velocity_and_step_size,
    set_area_detector_acquire_time,
)
from sm_bluesky.common.plans.fast_scan import fast_scan_grid
from sm_bluesky.log import LOGGER


class CleanUpArgs(TypedDict, total=False):
    Home: bool
    Origin: list[Motor | float]
    """Dictionary to store clean up options."""


@plan
@attach_data_session_metadata_decorator()
def grid_step_scan(
    dets: Sequence[Readable],
    count_time: float,
    x_step_motor: Motor,
    x_step_start: float,
    x_step_end: float,
    x_step_size: float,
    y_step_motor: Motor,
    y_step_start: float,
    y_step_end: float,
    y_step_size: float,
    home: bool = False,
    snake: bool = False,
    md: dict | None = None,
) -> MsgGenerator:
    """
    Standard Bluesky grid scan adapted to use step size.
    Optionally moves back to the original position after scan.

    Parameters
    ----------
    dets : Sequence[Readable]
        Area detectors or readable devices.
    count_time : float
        Detector count time.
    x_step_motor : Motor
        Motor for the X axis.
    x_step_start : float
        Starting position for x_step_motor.
    x_step_end : float
        Ending position for x_step_motor.
    x_step_size : float
        Step size for x motor.
    y_step_motor : Motor
        Motor for the Y axis.
    y_step_start : float
        Starting position for y_step_motor.
    y_step_end : float
        Ending position for y_step_motor.
    y_step_size : float
        Step size for y motor.
    home : bool, optional
        If True, move back to position before scan.
    snake : bool, optional
        If True, do grid scan without moving scan axis back to start position.
    md : dict, optional
        Metadata.

    Returns
    -------
    MsgGenerator
        A Bluesky generator for the scan.
    """
    # Check limits before doing anything
    yield from check_within_limit([x_step_start, x_step_end], x_step_motor)
    yield from check_within_limit([y_step_start, y_step_end], y_step_motor)

    clean_up_arg: CleanUpArgs = {"Home": home}
    if home:
        # Store original positions to return to after scan
        clean_up_arg["Origin"] = yield from get_motor_positions(
            x_step_motor, y_step_motor
        )  # type: ignore

    main_det = dets[0]
    if isinstance(main_det, AreaDetector | SingleTriggerDetector):
        yield from set_area_detector_acquire_time(main_det, acquire_time=count_time)

    # Add 1 to step number to include the end point
    x_num = step_size_to_step_num(x_step_start, x_step_end, x_step_size) + 1
    y_num = step_size_to_step_num(y_step_start, y_step_end, y_step_size) + 1

    yield from finalize_wrapper(
        plan=bp.grid_scan(
            dets,
            x_step_motor,
            x_step_start,
            x_step_end,
            x_num,
            y_step_motor,
            y_step_start,
            y_step_end,
            y_num,
            snake_axes=snake,
            md=md,
        ),
        final_plan=clean_up(clean_up_arg),
    )


@plan
@attach_data_session_metadata_decorator()
def grid_fast_scan(
    dets: list[Readable],
    count_time: float,
    step_motor: Motor,
    step_start: float,
    step_end: float,
    scan_motor: Motor,
    scan_start: float,
    scan_end: float,
    plan_time: float,
    point_correction: float = 1,
    step_size: float | None = None,
    home: bool = False,
    snake_axes: bool = True,
    md: dict[str, Any] | None = None,
) -> MsgGenerator:
    """
    Initiates a 2-axis scan, targeting a maximum scan speed of around 10Hz.
    Calculates the number of data points based on the detector's count time.
    If no step size is provided, aims for a uniform distribution of points.
    Adjusts scan speed and step size to fit the desired scan duration.

    Parameters
    ----------
    dets : list[Readable]
        List of detectors to use for the scan.
    count_time : float
        Detector count time.
    step_motor : Motor
        Motor for the slow axis.
    step_start : float
        Starting position for the step motor.
    step_end : float
        Ending position for the step motor.
    scan_motor : Motor
        Motor for the continuously moving axis.
    scan_start : float
        Starting position for the scan motor.
    scan_end : float
        Ending position for the scan motor.
    plan_time : float
        Desired duration of the scan in seconds.
    point_correction : float, optional
        Scaling factor for the number of points, by default 1.
    step_size : float, optional
        Step size for the slow axis, by default None.
    home : bool, optional
        If True, move back to the original position after the scan, by default False.
    snake_axes : bool, optional
        If True, perform a snake scan, by default True.
    md : dict, optional
        Metadata for the scan, by default None.

    Returns
    -------
    MsgGenerator
        A Bluesky generator for the scan.
    """
    clean_up_arg: CleanUpArgs = {"Home": home}
    yield from check_within_limit([scan_start, scan_end], scan_motor)
    yield from check_within_limit([step_start, step_end], step_motor)

    if home:
        clean_up_arg["Origin"] = yield from get_motor_positions(scan_motor, step_motor)  # type: ignore

    scan_acc = yield from bps.rd(scan_motor.acceleration_time)
    scan_motor_speed = yield from bps.rd(scan_motor.velocity)
    scan_motor_max_vel = yield from bps.rd(scan_motor.max_velocity)
    step_motor_speed = yield from bps.rd(step_motor.velocity)
    step_acc = yield from bps.rd(step_motor.acceleration_time)

    main_det = dets[0]
    if isinstance(main_det, AreaDetector):
        yield from set_area_detector_acquire_time(det=main_det, acquire_time=count_time)
        deadtime = main_det._controller.get_deadtime(count_time)  # noqa: SLF001
    elif isinstance(main_det, SingleTriggerDetector):
        yield from set_area_detector_acquire_time(det=main_det, acquire_time=count_time)
        deadtime = count_time
    else:
        deadtime = count_time

    ideal_velocity, ideal_step_size = estimate_speed_steps(
        plan_time=plan_time,
        deadtime=deadtime,
        step_start=step_start,
        step_end=step_end,
        step_size=step_size,
        step_speed=step_motor_speed,
        step_acceleration=step_acc,
        scan_start=scan_start,
        scan_end=scan_end,
        scan_speed=scan_motor_speed,
        scan_acceleration=scan_acc,
        scan_max_vel=scan_motor_max_vel,
        correction=point_correction,
        snake_axes=snake_axes,
    )

    velocity, ideal_step_size = yield from get_velocity_and_step_size(
        scan_motor,
        ideal_velocity,
        ideal_step_size,
    )
    num_of_step = step_size_to_step_num(step_start, step_end, ideal_step_size)
    LOGGER.info(
        f"Step size = {ideal_step_size}, {scan_motor.name}: velocity = {velocity}, "
        f"number of steps = {num_of_step}."
    )
    yield from finalize_wrapper(
        plan=fast_scan_grid(
            dets,
            step_motor,
            step_start,
            step_end,
            num_of_step,
            scan_motor,
            scan_start,
            scan_end,
            velocity,
            snake_axes=snake_axes,
            md=md,
        ),
        final_plan=clean_up(clean_up_arg),
    )


def clean_up(clean_up_arg: CleanUpArgs) -> MsgGenerator:
    LOGGER.info(f"Clean up: {list(clean_up_arg)}")
    if clean_up_arg.get("Home") and "Origin" in clean_up_arg:
        # Move motors back to stored position
        yield from bps.mov(*clean_up_arg["Origin"])


def estimate_speed_steps(
    plan_time: float,
    deadtime: float,
    step_start: float,
    step_end: float,
    step_size: float | None,
    step_acceleration: float,
    step_speed: float,
    scan_start: float,
    scan_end: float,
    scan_acceleration: float,
    scan_speed: float,
    scan_max_vel: float,
    snake_axes: bool,
    correction: float,
) -> tuple[float, float]:
    """
    Estimate the speed and step size for a scan.
    """
    step_range = abs(step_start - step_end)
    scan_range = abs(scan_start - scan_end)

    point_per_axis = estimate_axis_points(
        plan_time=plan_time,
        deadtime=deadtime,
        step_range=step_range,
        step_acceleration=step_acceleration,
        step_speed=step_speed,
        scan_range=scan_range,
        scan_acceleration=scan_acceleration,
        scan_speed=scan_speed,
        snake_axes=snake_axes,
    )

    point_per_step_axis = max(1, floor(point_per_axis * correction * step_range))
    point_per_scan_axis = max(1, floor(point_per_axis * correction * scan_range))

    # Ideal step size is evenly distributed points within the two axes.
    if step_size is not None:
        if step_size == 0:
            raise ValueError("Step_size is 0")
        ideal_step_size = abs(step_size)
    else:
        ideal_step_size = step_range / point_per_step_axis

    # ideal_velocity: speed that allows the required step size.
    if point_per_scan_axis <= 2:
        ideal_velocity = scan_max_vel
    else:
        ideal_velocity = scan_range / (
            (scan_range / ideal_step_size) * deadtime + scan_acceleration * 2
        )
    LOGGER.info(
        f"Ideal step size = {ideal_step_size}, velocity = {ideal_velocity}, "
        f"number of data points for step axis {point_per_step_axis}"
    )
    return ideal_velocity, ideal_step_size


def estimate_axis_points(
    plan_time: float,
    deadtime: float,
    step_range: float,
    step_acceleration: float,
    step_speed: float,
    scan_range: float,
    scan_acceleration: float,
    scan_speed: float,
    snake_axes: bool = True,
    num_points_per_axis: float | None = None,
) -> int:
    """
    Estimate the number of points per axis for a scan.
    """
    iteration_limit = 10  # Prevent infinite recursion
    iteration_count = 0

    if num_points_per_axis is None:
        num_points_per_axis = sqrt((plan_time / deadtime) / (scan_range * step_range))
    old_num_points_per_axis = num_points_per_axis

    while (
        iteration_count <= iteration_limit
        and abs(num_points_per_axis - old_num_points_per_axis) <= 0.49
    ):
        old_num_points_per_axis = num_points_per_axis

        point_step_axis = max(1, floor(num_points_per_axis * step_range))
        step_mv_time = point_step_axis * step_acceleration * 2 + step_range / step_speed

        if snake_axes:
            scan_mv_time = point_step_axis * (scan_acceleration * 2)
        else:
            point_scan_axis = max(1, floor(num_points_per_axis * scan_range))
            scan_mv_time = point_scan_axis * (scan_acceleration * 2) + (
                point_scan_axis - 1
            ) * (scan_range / scan_speed + scan_acceleration * 2)

        corrected_num_points = (plan_time - step_mv_time - scan_mv_time) / deadtime
        if corrected_num_points <= 0:
            raise ValueError(
                f"Plan time too short for the area and count time required. "
                f"Plan time: {plan_time}, Step move time: {step_mv_time}, "
                f"Scan move time: {scan_mv_time}, Deadtime: {deadtime}"
            )
        iteration_count += 1
        num_points_per_axis = corrected_num_points
    point_per_axis = sqrt(num_points_per_axis / (scan_range * step_range))
    return max(1, floor(point_per_axis))
