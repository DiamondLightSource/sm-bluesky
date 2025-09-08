from typing import Any

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from blueapi.core import MsgGenerator
from bluesky.preprocessors import (
    finalize_wrapper,
)
from bluesky.protocols import Readable
from bluesky.utils import plan, short_uid
from dodal.plan_stubs.data_session import attach_data_session_metadata_decorator
from numpy import linspace
from ophyd_async.core import FlyMotorInfo
from ophyd_async.epics.motor import Motor

from sm_bluesky.common.helper import add_extra_names_to_meta
from sm_bluesky.common.plan_stubs import (
    cache_speed,
    check_within_limit,
    fly_trigger_and_read,
    restore_speed,
)
from sm_bluesky.log import LOGGER


@plan
@attach_data_session_metadata_decorator()
def fast_scan_1d(
    dets: list[Readable],
    motor: Motor,
    start: float,
    end: float,
    motor_speed: float | None = None,
    md: dict[str, Any] | None = None,
) -> MsgGenerator:
    """
    Perform a fast scan along one axis.

    Parameters
    ----------
    dets : list[Readable]
        List of readable objects (e.g., detectors).
    motor : Motor
        The motor to move during the scan.
    start : float
        The starting position of the motor.
    end : float
        The ending position of the motor.
    motor_speed : Optional[float], optional
        The speed of the motor during the scan. If None,
        the motor's current speed is used.

    Returns
    -------
    MsgGenerator
        A Bluesky generator for the scan.
    """

    if md is None:
        md = {}

    @bpp.stage_decorator(dets)
    @bpp.run_decorator(md=md)
    def inner_fast_scan_1d(
        dets: list[Any],
        motor: Motor,
        start: float,
        end: float,
        motor_speed: float | None = None,
    ):
        yield from check_within_limit([start, end], motor)
        yield from _fast_scan_1d(dets, motor, start, end, motor_speed)

    yield from finalize_wrapper(
        plan=inner_fast_scan_1d(dets, motor, start, end, motor_speed),
        final_plan=clean_up(),
    )


@plan
@attach_data_session_metadata_decorator()
def fast_scan_grid(
    dets: list[Readable],
    step_motor: Motor,
    step_start: float,
    step_end: float,
    num_step: int,
    scan_motor: Motor,
    scan_start: float,
    scan_end: float,
    motor_speed: float | None = None,
    snake_axes: bool = False,
    md: dict[str, Any] | None = None,
) -> MsgGenerator:
    """
    Same as fast_scan_1d with an extra axis to step through forming a grid.

    Parameters
    ----------
    detectors : list
        list of 'readable' objects
    step_motor :
        Motor (moveable, readable)
    step_start :
        Starting position for slow/stepping motor.
    step_end :
        Ending position for step motro.
    num_step:
        Number of steps to take going from start to end.
    scan_motor:  Motor (moveable, readable)
        The motor that will not stop during measurements.
    scan_start:
        Scan motor starting position.
    scan_end:
        Scan motor ending position.
    motor_speed: float optional.
        Speed of the scanning motor during measurements.
        If None, it will use current speed.
    snake_axes:
        If Ture. Scan motor will start an other line where it ended.
    md:
        place holder for meta data for future.

    """
    if md is None:
        md = {}
    md = add_extra_names_to_meta(md, "detectors", [det.name for det in dets])
    md = add_extra_names_to_meta(md, "motors", [scan_motor.name, step_motor.name])

    @bpp.stage_decorator(dets)
    @bpp.run_decorator(md=md)
    def inner_fast_scan_grid(
        dets: list[Any],
        step_motor: Motor,
        step_start: float,
        step_end: float,
        num_step: int,
        scan_motor: Motor,
        scan_start: float,
        scan_end: float,
        motor_speed: float | None = None,
        snake_axes: bool = False,
    ):
        yield from check_within_limit([step_start, step_end], step_motor)
        yield from check_within_limit([scan_start, scan_end], scan_motor)
        steps = linspace(step_start, step_end, num_step, endpoint=True)
        if snake_axes:
            for cnt, step in enumerate(steps):
                yield from bps.abs_set(step_motor, step)
                if cnt % 2 == 0:
                    yield from _fast_scan_1d(
                        dets + [step_motor],
                        scan_motor,
                        scan_start,
                        scan_end,
                        motor_speed,
                    )
                else:
                    yield from _fast_scan_1d(
                        dets + [step_motor],
                        scan_motor,
                        scan_end,
                        scan_start,
                        motor_speed,
                    )
        else:
            for step in steps:
                yield from bps.abs_set(step_motor, step)
                yield from _fast_scan_1d(
                    dets + [step_motor], scan_motor, scan_start, scan_end, motor_speed
                )

    yield from finalize_wrapper(
        plan=inner_fast_scan_grid(
            dets,
            step_motor,
            step_start,
            step_end,
            num_step,
            scan_motor,
            scan_start,
            scan_end,
            motor_speed,
            snake_axes,
        ),
        final_plan=clean_up(),
    )


def clean_up():
    LOGGER.info("Clean up")
    # possibly use to move back to starting position.
    yield from bps.null()


@plan
def _fast_scan_1d(
    dets: list[Any],
    motor: Motor,
    start: float,
    end: float,
    motor_speed: float | None = None,
) -> MsgGenerator:
    """
    The logic for one axis fast scan, used in fast_scan_1d and fast_scan_grid

    In this scan:
    1) The motor moves to the starting point.
    2) The motor speed is changed
    3) The motor is set in motion toward the end point
    4) During this movement detectors are triggered and read out until
        the endpoint is reached or stopped.
    5) Clean up, reset motor speed.

    Note: This is purely software triggering which result in variable accuracy.
    However, fast scan does not require encoder and hardware setup and should
    work for all motor. It is most frequently use for alignment and
    slow motion measurements.

    Parameters
    ----------
    detectors : list
        list of 'readable' objects
    motor : Motor (moveable, readable)

    start: float
        starting position.
    end: float,
        ending position

    motor_speed: Optional[float] = None,
        The speed of the motor during scan
    """

    # read the current speed and store it
    old_speed: dict[Motor, float] = yield from cache_speed([motor])

    def inner_fast_scan_1d(
        dets: list[Any],
        motor: Motor,
        start: float,
        end: float,
        motor_speed: float | None = None,
    ):
        if not motor_speed:
            motor_speed = old_speed[motor]

        LOGGER.info(
            f"Starting 1d fly scan with {motor.name}:"
            + f" start position = {start}, end position = {end}."
        )

        grp = short_uid("prepare")
        fly_info = FlyMotorInfo(
            start_position=start,
            end_position=end,
            time_for_move=abs(start - end) / motor_speed,
        )
        yield from bps.prepare(motor, fly_info, group=grp, wait=True)
        yield from fly_trigger_and_read(motor, fly_info, dets)

    yield from finalize_wrapper(
        plan=inner_fast_scan_1d(dets, motor, start, end, motor_speed),
        final_plan=restore_speed(old_speed),
    )
