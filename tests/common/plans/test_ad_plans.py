from collections import defaultdict
from typing import Any

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


async def test_Andor2_trigger_img(
    RE: RunEngine, andor2: Andor2Detector, static_path_provider: StaticPathProvider
):
    docs = defaultdict(list)

    def capture_emitted(name: str, doc: Any):
        docs[name].append(doc)

    RE.subscribe(capture_emitted)

    set_mock_value(andor2.driver.detector_state, ADState.IDLE)

    RE(trigger_img(andor2, 4))

    assert (
        f"{static_path_provider._directory_path}/"
        == await andor2.fileio.file_path.get_value()
    )
    assert (
        str(static_path_provider._directory_path) + "/test-andor2-hdf0"
        == await andor2.fileio.full_file_name.get_value()
    )
    assert_emitted(
        docs, start=1, descriptor=1, stream_resource=1, stream_datum=1, event=1, stop=1
    )


async def test_Andor2_scan(
    RE: RunEngine,
    andor2: Andor2Detector,
    static_path_provider: StaticPathProvider,
    sim_motor: XYZStage,
):
    docs = defaultdict(list)

    def capture_emitted(name, doc):
        docs[name].append(doc)

    RE.subscribe(capture_emitted)
    set_mock_value(andor2.driver.detector_state, ADState.IDLE)
    RE(scan([andor2], sim_motor.y, -3, 3, 10))
    assert (
        f"{static_path_provider._directory_path}/"
        == await andor2.fileio.file_path.get_value()
    )
    assert (
        str(static_path_provider._directory_path) + "/test-andor2-hdf0"
        == await andor2.fileio.full_file_name.get_value()
    )
    assert_emitted(
        docs,
        start=1,
        descriptor=1,
        stream_resource=1,
        stream_datum=10,
        event=10,
        stop=1,
    )
