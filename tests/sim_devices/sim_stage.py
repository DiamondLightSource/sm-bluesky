import asyncio
import contextlib
import time

import numpy as np
from bluesky.protocols import (
    Flyable,
    Preparable,
    Stoppable,
)
from ophyd_async.core import (
    AsyncStatus,
    StandardReadable,
    WatchableAsyncStatus,
    WatcherUpdate,
    observe_value,
    soft_signal_r_and_setter,
    soft_signal_rw,
)
from ophyd_async.core import StandardReadableFormat as Format
from ophyd_async.epics.motor import FlyMotorInfo, MotorLimitsException


class SimRealMotor(
    StandardReadable,
    Stoppable,
    Flyable,
    Preparable,
):
    def __init__(self, name="", instant=True) -> None:
        """
        A simulated motor that mimics the behavior of a real motor. Unlike
         ophyd_async.sim.SimMotor, this class takes FlyMotorInfo rather than
         FlySimMotorInfo. This makes it better for testing plans, as it more
         closely represents a real motor's configuration.
        This only required for cases where plan supply motor speed.

        Simulated motor device
        args:
        - prefix: str: Signal names prefix
        - name: str: name of device
        - instant: bool: whether to move instantly, or with a delay
        """
        # Define some signals
        with self.add_children_as_readables(Format.HINTED_SIGNAL):
            self.user_readback, self._user_readback_set = soft_signal_r_and_setter(
                float, 0
            )
        with self.add_children_as_readables(Format.CONFIG_SIGNAL):
            self.velocity = soft_signal_rw(float, 0 if instant else 88.88)
            self.units = soft_signal_rw(str, "mm")
        self.user_setpoint = soft_signal_rw(float, 0)
        self.max_velocity = soft_signal_rw(float, 100)
        self.acceleration_time = soft_signal_rw(float, 0.0)
        self.precision = soft_signal_rw(int, 3)
        self.deadband = soft_signal_rw(float, 0.05)
        self.motor_done_move = soft_signal_rw(int, 1)
        self.low_limit_travel = soft_signal_rw(float, -100)
        self.high_limit_travel = soft_signal_rw(float, 100)
        # Whether set() should complete successfully or not
        self._set_success = True
        self._move_status: AsyncStatus | None = None
        super().__init__(name=name)

    async def _move(self, old_position: float, new_position: float, move_time: float):
        start = time.monotonic()
        # Make an array of relative update times at 10Hz intervals
        update_times = np.arange(0.1, move_time, 0.1)
        # With the end position appended
        update_times = np.concatenate((update_times, [move_time]))
        # Interpolate the [old, new] position array with those update times
        new_positions = np.interp(
            update_times, [0, move_time], [old_position, new_position]
        )
        for update_time, new_position in zip(update_times, new_positions, strict=True):  # type: ignore
            # Calculate how long to wait to get there
            relative_time = time.monotonic() - start
            await asyncio.sleep(update_time - relative_time)
            # Update the readback position
            self._user_readback_set(new_position)

    async def stop(self, success=True):
        """
        Stop the motor if it is moving
        """
        self._set_success = success
        if self._move_status:
            self._move_status.task.cancel()
            self._move_status = None
        await self.user_setpoint.set(await self.user_readback.get_value())

    @AsyncStatus.wrap
    async def prepare(self, value: FlyMotorInfo):
        """Calculate required velocity and run-up distance, then if motor limits aren't
        breached, move to start position minus run-up distance"""
        self._fly_timeout = value.timeout
        # Velocity, at which motor travels from start_position to end_position, in motor
        # egu/s.
        fly_velocity = await self._prepare_velocity(
            value.start_position,
            value.end_position,
            value.time_for_move,
        )
        # start_position with run_up_distance added on.
        fly_prepared_position = await self._prepare_motor_path(
            abs(fly_velocity), value.start_position, value.end_position
        )
        await self.set(fly_prepared_position)

    @AsyncStatus.wrap
    async def kickoff(self):
        """Begin moving motor from prepared position to final position."""
        assert self._fly_completed_position, (
            "Motor must be prepared before attempting to kickoff"
        )
        self._fly_status = self.set(self._fly_completed_position)

    def complete(self) -> WatchableAsyncStatus:
        """Mark as complete once motor reaches completed position."""
        assert self._fly_status, "kickoff not called"
        return self._fly_status

    async def _prepare_velocity(
        self, start_position: float, end_position: float, time_for_move: float
    ) -> float:
        fly_velocity = (start_position - end_position) / time_for_move
        max_speed, egu = await asyncio.gather(
            self.max_velocity.get_value(), self.units.get_value()
        )
        if abs(fly_velocity) > max_speed:
            raise MotorLimitsException(
                f"Motor speed of {abs(fly_velocity)} {egu}/s was requested for a motor "
                f" with max speed of {max_speed} {egu}/s"
            )
        await self.velocity.set(abs(fly_velocity))
        return fly_velocity

    async def _prepare_motor_path(
        self, fly_velocity: float, start_position: float, end_position: float
    ) -> float:
        # Distance required for motor to accelerate from stationary to fly_velocity, and
        # distance required for motor to decelerate from fly_velocity to stationary
        run_up_distance = (
            (await self.acceleration_time.get_value()) * fly_velocity * 0.5
        )
        self._fly_completed_position = end_position + run_up_distance
        # Prepared position not used after prepare, so no need to store in self
        fly_prepared_position = start_position - run_up_distance
        motor_lower_limit, motor_upper_limit, egu = await asyncio.gather(
            self.low_limit_travel.get_value(),
            self.high_limit_travel.get_value(),
            self.units.get_value(),
        )
        if (
            not motor_upper_limit >= fly_prepared_position >= motor_lower_limit
            or not motor_upper_limit
            >= self._fly_completed_position
            >= motor_lower_limit
        ):
            raise MotorLimitsException(
                f"Motor trajectory for requested fly is from "
                f"{fly_prepared_position}{egu} to "
                f"{self._fly_completed_position}{egu} but motor limits are "
                f"{motor_lower_limit}{egu} <= x <= {motor_upper_limit}{egu} "
            )
        return fly_prepared_position

    @WatchableAsyncStatus.wrap
    async def set(self, value: float):
        """
        Asynchronously move the motor to a new position.
        """
        # Make sure any existing move tasks are stopped
        await self.stop()
        old_position, units, velocity = await asyncio.gather(
            self.user_setpoint.get_value(),
            self.units.get_value(),
            self.velocity.get_value(),
        )
        # If zero velocity, do instant move
        move_time = abs(value - old_position) / velocity if velocity else 0
        self._move_status = AsyncStatus(self._move(old_position, value, move_time))
        # If stop is called then this will raise a CancelledError, ignore it
        with contextlib.suppress(asyncio.CancelledError):
            async for current_position in observe_value(
                self.user_readback, done_status=self._move_status
            ):
                yield WatcherUpdate(
                    current=current_position,
                    initial=old_position,
                    target=value,
                    name=self.name,
                    unit=units,
                )
        if not self._set_success:
            raise RuntimeError("Motor was stopped")


class SimStage(StandardReadable):
    """A simulated sample stage with X and Y movables."""

    def __init__(self, name="", instant=True) -> None:
        # Define some child Devices
        with self.add_children_as_readables():
            self.x = SimRealMotor(instant=instant)
            self.y = SimRealMotor(instant=instant)
            self.z = SimRealMotor(instant=instant)
        # Set name of device and child devices
        super().__init__(name=name)
