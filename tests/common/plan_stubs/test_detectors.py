import random

import pytest
from bluesky import RunEngine
from ophyd_async.core import get_mock_put, init_devices
from ophyd_async.epics.adcore import ADBaseIO, AreaDetector, SingleTriggerDetector

from sm_bluesky.common.plan_stubs import set_area_detector_acquire_time


@pytest.fixture
async def mock_single_trigger_det() -> SingleTriggerDetector:
    async with init_devices(mock=True):
        mock_single_trigger_det = SingleTriggerDetector(drv=ADBaseIO("p99-007"))
    return mock_single_trigger_det


def test_set_area_detector_acquire_time_setting_single_trigger_detector(
    mock_single_trigger_det: SingleTriggerDetector, run_engine: RunEngine
) -> None:
    count_time = random.uniform(0, 1)
    run_engine(set_area_detector_acquire_time(mock_single_trigger_det, count_time))
    get_mock_put(mock_single_trigger_det.drv.acquire_time).assert_awaited_once_with(
        count_time, wait=True
    )


def test_set_area_detector_acquire_time_setting_area_detector(
    andor2: AreaDetector, run_engine: RunEngine
) -> None:
    count_time = random.uniform(0, 1)
    run_engine(set_area_detector_acquire_time(andor2, count_time))
    get_mock_put(andor2.driver.acquire_time).assert_awaited_once_with(
        count_time, wait=True
    )
