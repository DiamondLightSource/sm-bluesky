from pathlib import Path
from unittest.mock import Mock

import pytest
from dodal.common.beamlines.beamline_utils import (
    set_path_provider,
)
from dodal.common.visit import (
    LocalDirectoryServiceClient,
    StaticVisitPathProvider,
)
from dodal.devices.motors import XYZStage
from ophyd_async.core import (
    FilenameProvider,
    StaticFilenameProvider,
    StaticPathProvider,
    init_devices,
)
from ophyd_async.epics.adandor import Andor2Detector
from ophyd_async.epics.adcore import ADBaseIO, SingleTriggerDetector
from ophyd_async.testing import callback_on_mock_put, set_mock_value

from sm_bluesky.common.sim_devices import SimDetector, SimStage

RECORD = str(Path(__file__).parent / "panda" / "db" / "panda.db")
INCOMPLETE_BLOCK_RECORD = str(
    Path(__file__).parent / "panda" / "db" / "incomplete_block_panda.db"
)
INCOMPLETE_RECORD = str(Path(__file__).parent / "panda" / "db" / "incomplete_panda.db")
EXTRA_BLOCKS_RECORD = str(
    Path(__file__).parent / "panda" / "db" / "extra_blocks_panda.db"
)


set_path_provider(
    StaticVisitPathProvider(
        "p99",
        Path("/dls/p99/data/2024/cm37284-2/processing/writenData"),
        client=LocalDirectoryServiceClient(),  # RemoteDirectoryServiceClient("http://p99-control:8088/api"),
    )
)

A_BIT = 0.5


pytest_plugins = ["dodal.testing.fixtures.run_engine"]


@pytest.fixture
def static_filename_provider() -> StaticFilenameProvider:
    return StaticFilenameProvider("ophyd_async_tests")


@pytest.fixture
def static_path_provider_factory(tmp_path: Path):
    def create_static_dir_provider_given_fp(fp: FilenameProvider):
        return StaticPathProvider(fp, tmp_path)

    return create_static_dir_provider_given_fp


@pytest.fixture
def static_path_provider(
    static_path_provider_factory,
    static_filename_provider: FilenameProvider,
):
    return static_path_provider_factory(static_filename_provider)


@pytest.fixture
async def sim_motor() -> XYZStage:
    async with init_devices(mock=True):
        sim_motor = XYZStage("BLxxI-MO-TABLE-01:X", name="sim_motor")
    set_mock_value(sim_motor.x.velocity, 2.78)
    set_mock_value(sim_motor.x.high_limit_travel, 8.168)
    set_mock_value(sim_motor.x.low_limit_travel, -8.888)
    set_mock_value(sim_motor.x.user_readback, 1)
    set_mock_value(sim_motor.x.motor_egu, "mm")
    set_mock_value(sim_motor.x.motor_done_move, True)
    set_mock_value(sim_motor.x.max_velocity, 100)

    set_mock_value(sim_motor.y.motor_egu, "mm")
    set_mock_value(sim_motor.y.high_limit_travel, 5.168)
    set_mock_value(sim_motor.y.low_limit_travel, -5.888)
    set_mock_value(sim_motor.y.user_readback, 0)
    set_mock_value(sim_motor.y.motor_egu, "mm")
    set_mock_value(sim_motor.y.velocity, 2.88)
    set_mock_value(sim_motor.y.motor_done_move, True)
    set_mock_value(sim_motor.y.max_velocity, 100)

    set_mock_value(sim_motor.z.motor_egu, "mm")
    set_mock_value(sim_motor.z.high_limit_travel, 5.168)
    set_mock_value(sim_motor.z.low_limit_travel, -5.888)
    set_mock_value(sim_motor.z.user_readback, 0)
    set_mock_value(sim_motor.z.motor_egu, "mm")
    set_mock_value(sim_motor.z.velocity, 2.88)
    set_mock_value(sim_motor.z.motor_done_move, True)
    set_mock_value(sim_motor.z.max_velocity, 100)

    return sim_motor


@pytest.fixture
async def sim_stage_step() -> SimStage:
    async with init_devices(mock=True):
        sim_stage_step = SimStage(name="sim_stage_step", instant=True)
    return sim_stage_step


@pytest.fixture
async def sim_stage_delay() -> SimStage:
    async with init_devices(mock=True):
        sim_stage_delay = SimStage(name="sim_stage_delay", instant=False)
    set_mock_value(sim_stage_delay.x.velocity, 88.88)
    set_mock_value(sim_stage_delay.x.acceleration_time, 0.01)
    set_mock_value(sim_stage_delay.y.velocity, 88.88)
    set_mock_value(sim_stage_delay.y.acceleration_time, 0.01)
    set_mock_value(sim_stage_delay.z.velocity, 88.88)
    set_mock_value(sim_stage_delay.z.acceleration_time, 0.01)
    return sim_stage_delay


@pytest.fixture
async def fake_detector() -> SimDetector:
    async with init_devices(mock=True):
        fake_detector = SimDetector(prefix="fake_Pv", name="fake_detector")
    set_mock_value(fake_detector.value, 0)
    return fake_detector


# area detector that is use for testing
@pytest.fixture
async def andor2(static_path_provider: StaticPathProvider) -> Andor2Detector:
    async with init_devices(mock=True):
        andor2 = Andor2Detector("p99", static_path_provider)

    set_mock_value(andor2.driver.array_size_x, 10)
    set_mock_value(andor2.driver.array_size_y, 20)
    set_mock_value(andor2.fileio.file_path_exists, True)
    set_mock_value(andor2.fileio.num_captured, 0)
    set_mock_value(andor2.fileio.file_path, str(static_path_provider._directory_path))
    set_mock_value(
        andor2.fileio.full_file_name,
        str(static_path_provider._directory_path) + "/test-andor2-hdf0",
    )

    rbv_mocks = Mock()
    rbv_mocks.get.side_effect = range(0, 10000)
    callback_on_mock_put(
        andor2.fileio.capture,
        lambda *_, **__: set_mock_value(andor2.fileio.capture, value=True),
    )

    callback_on_mock_put(
        andor2.driver.acquire,
        lambda *_, **__: set_mock_value(andor2.fileio.num_captured, rbv_mocks.get()),
    )

    return andor2


# area detector point that is use for testing
@pytest.fixture
async def andor2_point() -> SingleTriggerDetector:
    async with init_devices(mock=True):
        andor2_point = SingleTriggerDetector(drv=ADBaseIO("p99"))

    return andor2_point
