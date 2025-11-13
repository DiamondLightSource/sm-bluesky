from collections.abc import Mapping

from bluesky.plans import scan
from bluesky.run_engine import RunEngine
from dodal.devices.motors import XYZStage
from ophyd_async.core import (
    StaticPathProvider,
)
from ophyd_async.epics.adandor import Andor2Detector
from ophyd_async.epics.adcore import ADState
from ophyd_async.testing import assert_emitted, set_mock_value

from sm_bluesky.common.plans import trigger_img


async def test_andor2_trigger_img(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    andor2: Andor2Detector,
    static_path_provider: StaticPathProvider,
) -> None:
    set_mock_value(andor2.driver.detector_state, ADState.IDLE)
    run_engine(trigger_img(andor2, 4))
    assert (
        f"{static_path_provider._directory_path}/"
        == await andor2.fileio.file_path.get_value()
    )
    assert (
        str(static_path_provider._directory_path) + "/test-andor2-hdf0"
        == await andor2.fileio.full_file_name.get_value()
    )
    assert_emitted(
        run_engine_documents,
        start=1,
        descriptor=1,
        stream_resource=1,
        stream_datum=1,
        event=1,
        stop=1,
    )


async def test_andor2_scan(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    andor2: Andor2Detector,
    static_path_provider: StaticPathProvider,
    sim_motor: XYZStage,
) -> None:
    set_mock_value(andor2.driver.detector_state, ADState.IDLE)
    run_engine(scan([andor2], sim_motor.y, -3, 3, 10))
    assert (
        f"{static_path_provider._directory_path}/"
        == await andor2.fileio.file_path.get_value()
    )
    assert (
        str(static_path_provider._directory_path) + "/test-andor2-hdf0"
        == await andor2.fileio.full_file_name.get_value()
    )
    assert_emitted(
        run_engine_documents,
        start=1,
        descriptor=1,
        stream_resource=1,
        stream_datum=10,
        event=10,
        stop=1,
    )
