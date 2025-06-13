from collections.abc import Hashable, Iterator
from typing import Any

import bluesky.plan_stubs as bps
from bluesky.plan_stubs import abs_set
from bluesky.utils import MsgGenerator, plan
from dodal.devices.slits import Slits
from ophyd_async.epics.motor import Motor
from pydantic import RootModel

from sm_bluesky.log import LOGGER


class MotorTable(RootModel):
    """RootModel for motor tables"""

    root: dict[str, float]


@plan
def move_motor_with_look_up(
    slit: Motor,
    size: float,
    motor_table: dict[str, float],
    use_motor_position: bool = False,
    wait: bool = True,
    group: Hashable | None = None,
) -> MsgGenerator:
    """Perform a step scan with the range and starting motor position
      given/calculated by using a look up table(dictionary).
      Move to the peak position after the scan and update the lookup table.

    Parameters
    ----------
    motor: Motor
        Motor devices that is being centre.
    size: float
        The motor position or name in the motor_table.
    motor_table: dict[str, float],
        Look up table for motor position,
    use_motor_position: bool = False,
        If Ture it will take motor position as size.
    wait: bool = True,
        If Ture, it will wait until position is reached.
    group: Hashable | None = None,
        Bluesky group identifier used by ‘wait’.

    """
    MotorTable.model_validate(motor_table)
    if use_motor_position:
        yield from abs_set(slit, size, wait=wait, group=group)
    elif str(int(size)) in motor_table:
        yield from abs_set(slit, motor_table[str(int(size))], wait=wait, group=group)
    else:
        raise ValueError(
            f"No slit with size={size}. Available slit size: {motor_table}"
        )


@plan
def set_slit_size(
    xy_slit: Slits,
    x_size: float,
    y_size: float | None = None,
    wait: bool = True,
    group: Hashable | None = None,
) -> MsgGenerator:
    """Set opening of x-y slit.

    Parameters
    ----------
    xy_slit: Slits
        A slits device.
    x_size: float
        The x opening size.
    y_size: float
        The y opening size.
    wait: bool
        If this is True it will wait for all motions to finish.
    group (optional): Hashable
        Bluesky group identifier used by ‘wait’.
    """

    if wait and group is None:
        group = f"{xy_slit.name}_wait"
    if y_size is None:
        y_size = x_size
    LOGGER.info(f"Setting {xy_slit.name} to x = {x_size}, y = {y_size}.")
    yield from bps.abs_set(xy_slit.x_gap, x_size, group=group)
    yield from bps.abs_set(xy_slit.y_gap, y_size, group=group)
    if wait:
        LOGGER.info(f"Waiting for {xy_slit.name} to finish move.")
        yield from bps.wait(group=group)


@plan
def check_within_limit(values: list[float], motor: Motor):
    """Check if the given values are within the limits of the motor.
    Parameters
    ----------
    values : List[float]
        The values to check.
    motor : Motor
        The motor to check the limits of.

    Raises
    ------
    ValueError
        If any value is outside the motor's limits.
    """
    LOGGER.info(f"Check {motor.name} limits.")
    lower_limit = yield from bps.rd(motor.low_limit_travel)
    high_limit = yield from bps.rd(motor.high_limit_travel)
    for value in values:
        if not lower_limit < value < high_limit:
            raise ValueError(
                f"{motor.name} move request of {value} is beyond limits:"
                f"{lower_limit} < {high_limit}"
            )


def get_motor_positions(*arg: Motor) -> Iterator[tuple[str, float]]:
    """
    Get the motor positions of the given motors and store them in a list.

    Parameters
    ----------
    arg : Motor
        The motors to get the positions of.

    Returns
    -------
    Iterator[Tuple[str, float]]
        An iterator of tuples containing the motor name and its position.
    """
    motor_position = []
    for motor in arg:
        motor_position.append(motor)
        position = yield from bps.rd(motor)  # type: ignore
        motor_position.append(position)

    LOGGER.info(f"Stored motor, position  = {motor_position}.")
    return motor_position


def get_velocity_and_step_size(
    scan_motor: Motor, ideal_velocity: float, ideal_step_size: float
) -> Iterator[Any]:
    """
    Adjust the step size if the required velocity is higher than the max value.

    Parameters
    ----------
    scan_motor : Motor
        The motor which will move continuously.
    ideal_velocity : float
        The desired velocity.
    ideal_step_size : float
        The non-scanning motor step size.

    Returns
    -------
    Iterator[Tuple[float, float]]
        An iterator containing the adjusted velocity and step size.
    """
    if ideal_velocity <= 0.0:
        raise ValueError(f"{scan_motor.name} speed: {ideal_velocity} <= 0")
    max_velocity = yield from bps.rd(scan_motor.max_velocity)  # type: ignore
    # if motor does not move fast enough increase step_motor step size
    if ideal_velocity > max_velocity:
        ideal_step_size = ideal_step_size / (ideal_velocity / max_velocity)
        ideal_velocity = round(max_velocity, 3)

    return ideal_velocity, ideal_step_size
