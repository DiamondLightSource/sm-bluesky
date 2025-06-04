import os

from dodal.devices.electron_analyser import (
    ElectronAnalyserDetector,
)
from dodal.devices.electron_analyser.specs import SpecsDetector
from ophyd_async.core import init_devices
from ophyd_async.epics.motor import Motor
from ophyd_async.testing import set_mock_value

TEST_DATA_PATH = "tests/test_data/electron_analyser/"

TEST_VGSCIENTA_SEQUENCE = os.path.join(TEST_DATA_PATH, "vgscienta_sequence.seq")
TEST_SPECS_SEQUENCE = os.path.join(TEST_DATA_PATH, "specs_sequence.seq")


def analyser_setup_for_scan(sim_analyser: ElectronAnalyserDetector):
    if isinstance(sim_analyser, SpecsDetector):
        # Needed so we don't run into divide by zero errors on read and describe.
        dummy_val = 10
        set_mock_value(sim_analyser.driver.min_angle_axis, dummy_val)
        set_mock_value(sim_analyser.driver.max_angle_axis, dummy_val)
        set_mock_value(sim_analyser.driver.slices, dummy_val)
        set_mock_value(sim_analyser.driver.low_energy, dummy_val)
        set_mock_value(sim_analyser.driver.high_energy, dummy_val)


async def create_motor(name: str) -> Motor:
    async with init_devices(mock=True, connect=True):
        sim_motor = Motor(prefix="TEST:", name=name)
    # Needed so we don't get divide by zero errors when used in a scan.
    set_mock_value(sim_motor.velocity, 1)
    return sim_motor
