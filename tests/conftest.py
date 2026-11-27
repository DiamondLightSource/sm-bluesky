from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from daq_config_server.client import ConfigClient
from daq_config_server.testing import MockServerResponse, PathToMockDataDict
from dodal.common.beamlines.beamline_utils import (
    set_path_provider,
)
from dodal.common.visit import (
    LocalDirectoryServiceClient,
    StaticVisitPathProvider,
)
from dodal.devices.motors import XYZStage
from dodal.devices.single_trigger_detector import SingleTriggerDetector
from ophyd_async.core import (
    FilenameProvider,
    StaticFilenameProvider,
    StaticPathProvider,
    callback_on_mock_put,
    init_devices,
    set_mock_value,
)
from ophyd_async.epics.adandor import AndorDetector
from ophyd_async.epics.adcore import ADBaseIO, ADWriterFactory
from ophyd_async.epics.adcore._io import NDPluginFileIO
from ophyd_async.epics.motor import VeloAndAcclRespectingMotorMock

from tests.helpers import FakeDetector

RECORD = str(Path(__file__).parent / "panda" / "db" / "panda.db")
INCOMPLETE_BLOCK_RECORD = str(
    Path(__file__).parent / "panda" / "db" / "incomplete_block_panda.db"
)
INCOMPLETE_RECORD = str(Path(__file__).parent / "panda" / "db" / "incomplete_panda.db")
EXTRA_BLOCKS_RECORD = str(
    Path(__file__).parent / "panda" / "db" / "extra_blocks_panda.db"
)


@pytest.fixture
def path_to_mock_data() -> PathToMockDataDict:
    return {}


@pytest.fixture
def mock_config_client(path_to_mock_data: PathToMockDataDict) -> ConfigClient:
    return ConfigClient(server_response=MockServerResponse(path_to_mock_data))


set_path_provider(
    StaticVisitPathProvider(
        "p99",
        Path("/dls/p99/data/2024/cm37284-2/processing/writenData"),
        client=LocalDirectoryServiceClient(),  # RemoteDirectoryServiceClient("http://p99-control:8088/api"),
    )
)

A_BIT = 0.5


pytest_plugins = ["dodal.testing.fixtures.run_engine"]


@pytest.fixture(autouse=True)
def allow_bluesky_verb_override(monkeypatch: pytest.MonkeyPatch) -> None:
    # This is a temp work around until we fix whole repo
    monkeypatch.setenv("OPHYD_ASYNC_ALLOW_RESERVED_ATTRS", "YES")


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
async def sim_stage() -> XYZStage:
    """XYZStage whose motors move instantly (the default Motor mock)."""
    async with init_devices(mock=True):
        sim_stage = XYZStage("BLxxI-MO-STAGE-01:", name="sim_stage")
    for motor in (sim_stage.x, sim_stage.y, sim_stage.z):
        set_mock_value(motor.low_limit_travel, -100)
        set_mock_value(motor.high_limit_travel, 100)
    return sim_stage


@pytest.fixture
async def sim_stage_delay() -> XYZStage:
    """XYZStage whose motors take time to move, respecting velocity and
    acceleration time."""
    sim_stage_delay = XYZStage("BLxxI-MO-STAGE-02:", name="sim_stage_delay")
    for motor in (sim_stage_delay.x, sim_stage_delay.y, sim_stage_delay.z):
        await motor.connect(mock=VeloAndAcclRespectingMotorMock())
        set_mock_value(motor.velocity, 88.88)
        set_mock_value(motor.acceleration_time, 0.01)
        set_mock_value(motor.low_limit_travel, -100)
        set_mock_value(motor.high_limit_travel, 100)
    return sim_stage_delay


@pytest.fixture
async def fake_detector() -> FakeDetector:
    async with init_devices(mock=True):
        fake_detector = FakeDetector()
    return fake_detector


# area detector that is use for testing
@pytest.fixture
async def andor2(static_path_provider: StaticPathProvider) -> AndorDetector:
    async with init_devices(mock=True):
        writer = ADWriterFactory.hdf(static_path_provider, writer_name="fileio")
        andor2 = AndorDetector("p99", writer)
    set_mock_value(andor2.driver.array_size_x, 10)
    set_mock_value(andor2.driver.array_size_y, 20)
    writer_inst = getattr(andor2, "fileio", None) or getattr(andor2, "hdf", None)
    if writer_inst is None:
        for name in dir(andor2):
            try:
                val = getattr(andor2, name)
            except Exception:
                continue
            if isinstance(val, NDPluginFileIO):
                writer_inst = val
                break
    if writer_inst is None:
        raise RuntimeError("Could not find file-writer plugin on andor2 detector")

    set_mock_value(writer_inst.file_path_exists, True)
    set_mock_value(writer_inst.num_captured, 0)
    set_mock_value(writer_inst.file_path, str(static_path_provider._directory_path))
    set_mock_value(
        writer_inst.full_file_name,
        str(static_path_provider._directory_path) + "/test-andor2-hdf0",
    )

    rbv_mocks = Mock()
    rbv_mocks.get.side_effect = range(0, 10000)
    callback_on_mock_put(
        writer_inst.capture,
        lambda *_, **__: set_mock_value(writer_inst.capture, value=True),
    )

    callback_on_mock_put(
        andor2.driver.acquire,
        lambda *_, **__: set_mock_value(writer_inst.num_captured, rbv_mocks.get()),
    )

    return andor2


# area detector point that is use for testing
@pytest.fixture
async def andor2_point() -> SingleTriggerDetector:
    async with init_devices(mock=True):
        andor2_point = SingleTriggerDetector(drv=ADBaseIO("p99"))

    return andor2_point


@pytest.fixture(autouse=True)
def mock_global_expanduser(tmp_path: Path):
    import os

    original_expanduser = os.path.expanduser

    def _expanduser(path: str) -> str:
        if path == "~":
            return str(tmp_path)
        if path.startswith("~/"):
            return str(tmp_path / path[2:])
        return original_expanduser(path)

    with patch("os.path.expanduser", side_effect=_expanduser):
        yield
