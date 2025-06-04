import asyncio
from collections.abc import Sequence
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call

import pytest
from bluesky import RunEngine
from bluesky import plan_stubs as bps
from bluesky.protocols import Movable, Readable, Triggerable
from dodal.devices.electron_analyser import (
    ElectronAnalyserDetector,
    ElectronAnalyserRegionDetector,
)
from dodal.devices.electron_analyser.abstract import (
    AbstractAnalyserDriverIO,
    AbstractBaseRegion,
    AbstractBaseSequence,
)
from dodal.devices.electron_analyser.specs import SpecsDetector
from dodal.devices.electron_analyser.vgscienta import VGScientaDetector
from ophyd.status import Status

from sm_bluesky.electron_analyser.plan_stubs import analyser_per_step as aps
from tests.electron_analyser.util import analyser_setup_for_scan, create_motor

ElectronAnalyserDetectorAlias = ElectronAnalyserDetector[
    AbstractAnalyserDriverIO, AbstractBaseSequence, AbstractBaseRegion
]
ElectronAnalyserRegionDetectorAlias = ElectronAnalyserRegionDetector[
    AbstractAnalyserDriverIO, AbstractBaseRegion
]


@pytest.fixture(params=[VGScientaDetector, SpecsDetector])
def detector_class(
    request: pytest.FixtureRequest,
) -> type[ElectronAnalyserDetector]:
    return request.param


@pytest.fixture
def region_detectors(
    sim_analyser: ElectronAnalyserDetector, sequence_file: str
) -> Sequence[ElectronAnalyserRegionDetector]:
    analyser_setup_for_scan(sim_analyser)
    return sim_analyser.create_region_detector_list(sequence_file)


@pytest.fixture(params=[0, 1, 2])
async def other_detectors(
    request: pytest.FixtureRequest,
) -> list[Readable]:
    return [await create_motor("det" + str(i + 1)) for i in range(request.param)]


@pytest.fixture
def all_detectors(
    region_detectors: Sequence[Readable], other_detectors: Sequence[Readable]
) -> Sequence[Readable]:
    return list(region_detectors) + list(other_detectors)


@pytest.fixture
def step() -> dict[Movable, Any]:
    return {}


@pytest.fixture
def pos_cache() -> dict[Movable, Any]:
    return {}


def run_engine_setup_decorator(func):
    def wrapper(all_detectors, step, pos_cache):
        yield from bps.open_run()
        yield from bps.stage_all(*all_detectors)
        yield from func(all_detectors, step, pos_cache)
        yield from bps.unstage_all(*all_detectors)
        yield from bps.close_run()

    return wrapper


def fake_status(region=None):
    status = Status()
    status.set_finished()
    return status


def test_analyser_nd_step_func_has_expected_driver_set_calls(
    all_detectors: Sequence[Readable],
    sim_analyser: ElectronAnalyserDetectorAlias,
    region_detectors: Sequence[ElectronAnalyserRegionDetectorAlias],
    step: dict[Movable, Any],
    pos_cache: dict[Movable, Any],
    RE: RunEngine,
) -> None:
    # Mock driver.set to track expected calls
    driver = sim_analyser.driver
    driver.set = MagicMock(side_effect=fake_status)
    expected_driver_set_calls = [call(r_det.region) for r_det in region_detectors]

    # Wrap our function to test with RunEngine setup.
    analyser_nd_step = run_engine_setup_decorator(aps.analyser_nd_step)

    RE(analyser_nd_step(all_detectors, step, pos_cache))

    # Our driver instance is shared between each region detector instance.
    # Check that each driver.set was called once with the correct region
    assert driver.set.call_args_list == expected_driver_set_calls


async def test_analyser_nd_step_func_calls_detectors_trigger_and_read_correctly(
    all_detectors: Sequence[Readable],
    other_detectors: Sequence[Readable],
    region_detectors: Sequence[ElectronAnalyserRegionDetectorAlias],
    step: dict[Movable, Any],
    pos_cache: dict[Movable, Any],
    RE: RunEngine,
) -> None:
    # Wrap our function to test with RunEngine setup.
    analyser_nd_step = run_engine_setup_decorator(aps.analyser_nd_step)

    for det in other_detectors:
        if isinstance(det, Triggerable):
            det.trigger = MagicMock(side_effect=fake_status)

        # Check if detector needs to be mocked with async or not.
        if asyncio.iscoroutinefunction(det.read):
            det.read = AsyncMock(return_value=await det.read())
        else:
            det.read = MagicMock(return_value=det.read())

    for r_det in region_detectors:
        r_det.trigger = MagicMock(side_effect=fake_status)
        r_det.read = MagicMock(return_value=r_det.read())

    RE(analyser_nd_step(all_detectors, step, pos_cache))

    for r_det in region_detectors:
        r_det.trigger.assert_called_once()  # type: ignore
        r_det.read.assert_called_once()  # type: ignore

    # Check that the other detectors are triggered and read by the number of region
    # detectors.
    for det in other_detectors:
        if isinstance(det, Triggerable):
            assert det.trigger.call_count == len(region_detectors)  # type: ignore
        assert det.read.call_count == len(region_detectors)  # type: ignore
