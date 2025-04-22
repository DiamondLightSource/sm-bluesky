from typing import Any

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from blueapi.core import MsgGenerator
from bluesky.preprocessors import (
    finalize_wrapper,
)
from bluesky.protocols import Readable
from bluesky.utils import short_uid
from numpy import linspace
from ophyd_async.epics.motor import FlyMotorInfo, Motor

from sm_bluesky.common.plan_stubs import check_within_limit
from sm_bluesky.log import LOGGER


def fast_scan_1d(
    dets: list[Any],
    motor: Motor,
    start: float,
    end: float,
    motor_speed: float | None = None,
) -> MsgGenerator:
    """
    One axis fast scan, using _fast_scan_1d.

    Parameters
    ----------
    detectors : list
        list of 'readable',triggerable  objects
    motor : Motor (moveable, readable)

    start: float
        starting position.
    end: float,
        ending position

    motor_speed: Optional[float] = None,
        The speed of the motor during scan
    """

    @bpp.stage_decorator(dets)
    @bpp.run_decorator()
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
    md: dict | None = None,
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

    @bpp.stage_decorator(dets)
    @bpp.run_decorator()
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


def reset_speed(old_speed, motor: Motor):
    LOGGER.info(f"Clean up: setting motor speed to {old_speed}.")
    if old_speed:
        yield from bps.abs_set(motor.velocity, old_speed)


def clean_up():
    LOGGER.info("Clean up")
    # possibly use to move back to starting position.
    yield from bps.null()


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
    old_speed: float = yield from bps.rd(motor.velocity)

    def inner_fast_scan_1d(
        dets: list[Any],
        motor: Motor,
        start: float,
        end: float,
        motor_speed: float | None = None,
    ):
        if not motor_speed:
            motor_speed = old_speed

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
        yield from bps.wait(group=grp)
        yield from bps.kickoff(motor, group=grp, wait=True)
        LOGGER.info(f"flying motor =  {motor.name} at speed = {motor_speed}")
        done = yield from bps.complete(motor)
        yield from bps.trigger_and_read(dets + [motor])
        while not done.done:
            yield from bps.trigger_and_read(dets + [motor])
            yield from bps.checkpoint()

    yield from finalize_wrapper(
        plan=inner_fast_scan_1d(dets, motor, start, end, motor_speed),
        final_plan=reset_speed(old_speed, motor),
    )
