from ophyd_async.core import (
    StandardReadable,
    soft_signal_rw,
)
from ophyd_async.sim import SimMotor


class SimMotorLimited(SimMotor):
    def __init__(self, name="", instant=True):
        self.high_limit_travel = soft_signal_rw(int, 100)
        self.low_limit_travel = soft_signal_rw(int, -100)

        super().__init__(name, instant)


class SimStage(StandardReadable):
    """A simulated sample stage with X and Y movables."""

    def __init__(self, name="", instant=True) -> None:
        # Define some child Devices
        with self.add_children_as_readables():
            self.x = SimMotorLimited(instant=instant)
            self.y = SimMotorLimited(instant=instant)
            self.z = SimMotorLimited(instant=instant)
        # Set name of device and child devices
        super().__init__(name=name)
