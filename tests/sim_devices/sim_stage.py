from ophyd_async.core import (
    StandardReadable,
    soft_signal_rw,
)
from ophyd_async.sim import SimMotor


class SimMotorExtra(SimMotor):
    def __init__(self, name="", instant=True) -> None:
        """
        SimMotor with extra signal
        """
        # Define some signals

        self.max_velocity = soft_signal_rw(float, 100)
        self.low_limit_travel = soft_signal_rw(float, -100)
        self.high_limit_travel = soft_signal_rw(float, 100)

        super().__init__(name=name, instant=instant)


class SimStage(StandardReadable):
    """A simulated sample stage with X and Y movables."""

    def __init__(self, name="", instant=True) -> None:
        # Define some child Devices
        with self.add_children_as_readables():
            self.x = SimMotorExtra(instant=instant)
            self.y = SimMotorExtra(instant=instant)
            self.z = SimMotorExtra(instant=instant)
        # Set name of device and child devices
        super().__init__(name=name)
