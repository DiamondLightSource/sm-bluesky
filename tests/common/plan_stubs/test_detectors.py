import random

import pytest
from ophyd_async.core import (
    init_devices,
)
from ophyd_async.epics.adcore import ADBaseIO, AreaDetector, SingleTriggerDetector
from ophyd_async.testing import get_mock_put

from sm_bluesky.common.plans_stubs import set_area_detector_acquire_time


@pytest.fixture
async def mock_single_trigger_det() -> SingleTriggerDetector:
    async with init_devices(mock=True):
        mock_single_trigger_det = SingleTriggerDetector(drv=ADBaseIO("p99-007"))
    return mock_single_trigger_det


def test_set_area_detector_acquire_time_setting_SingleTriggerDector(
    mock_single_trigger_det: SingleTriggerDetector, RE
):
    count_time = random.uniform(0, 1)
    RE(set_area_detector_acquire_time(mock_single_trigger_det, count_time))
    get_mock_put(mock_single_trigger_det.drv.acquire_time).assert_awaited_once_with(
        count_time, wait=True
    )


def test_set_area_detector_acquire_time_setting_AreaDetector(andor2: AreaDetector, RE):
    count_time = random.uniform(0, 1)
    RE(set_area_detector_acquire_time(andor2, count_time))
    get_mock_put(andor2.driver.acquire_time).assert_awaited_once_with(
        count_time, wait=True
    )
