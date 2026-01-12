from dodal.devices.electron_analyser.base import (
    ElectronAnalyserDetector,
)
from dodal.devices.electron_analyser.specs import SpecsDetector
from ophyd_async.core import set_mock_value


def analyser_setup_for_scan(sim_analyser: ElectronAnalyserDetector):
    if isinstance(sim_analyser, SpecsDetector):
        # Needed so we don't run into divide by zero errors on read and describe.
        dummy_val = 10
        set_mock_value(sim_analyser.driver.min_angle_axis, dummy_val)
        set_mock_value(sim_analyser.driver.max_angle_axis, dummy_val)
        set_mock_value(sim_analyser.driver.slices, dummy_val)
        set_mock_value(sim_analyser.driver.low_energy, dummy_val)
        set_mock_value(sim_analyser.driver.high_energy, dummy_val)
