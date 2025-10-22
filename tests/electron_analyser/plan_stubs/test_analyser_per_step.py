import asyncio
from collections import defaultdict
from collections.abc import Callable, Sequence
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call

import numpy as np
import pytest
from bluesky import RunEngine
from bluesky import plan_stubs as bps
from bluesky.protocols import Movable, Readable, Triggerable
from dodal.devices.electron_analyser import (
    ElectronAnalyserDetector,
    ElectronAnalyserRegionDetector,
    GenericElectronAnalyserDetector,
    GenericElectronAnalyserRegionDetector,
)
from ophyd.status import Status
from ophyd_async.sim import SimMotor

from sm_bluesky.electron_analyser.plan_stubs import analyser_per_step as aps
from tests.electron_analyser.util import analyser_setup_for_scan


@pytest.fixture
def region_detectors(
    sim_analyser: ElectronAnalyserDetector, sequence_file: str
) -> Sequence[ElectronAnalyserRegionDetector]:
    analyser_setup_for_scan(sim_analyser)
    return sim_analyser.create_region_detector_list(sequence_file)


@pytest.fixture(params=[0, 1, 2])
def other_detectors(
    request: pytest.FixtureRequest,
) -> list[Readable]:
    return [SimMotor("det" + str(i + 1)) for i in range(request.param)]


@pytest.fixture
def all_detectors(
    region_detectors: Sequence[Readable], other_detectors: Sequence[Readable]
) -> Sequence[Readable]:
    return list(region_detectors) + list(other_detectors)


@pytest.fixture
def step() -> dict[Movable, Any]:
    return {
        SimMotor("motor1"): np.float64(20),
        SimMotor("motor2"): np.float64(10),
    }


@pytest.fixture
def pos_cache() -> dict[Movable, Any]:
    return defaultdict(lambda: 0)


def run_engine_setup_decorator(func):
    def wrapper(all_detectors, step, pos_cache):
        yield from bps.open_run()
        yield from bps.stage_all(*all_detectors)
        yield from func(all_detectors, step, pos_cache)
        yield from bps.unstage_all(*all_detectors)
        yield from bps.close_run()

    return wrapper


@pytest.fixture
def analyser_nd_step() -> Callable:
    return run_engine_setup_decorator(aps.analyser_nd_step)


def fake_status(region=None) -> Status:
    status = Status()
    status.set_finished()
    return status


def test_analyser_nd_step_func_has_expected_driver_set_calls(
    run_engine: RunEngine,
    analyser_nd_step: Callable,
    all_detectors: Sequence[Readable],
    sim_analyser: GenericElectronAnalyserDetector,
    region_detectors: Sequence[GenericElectronAnalyserRegionDetector],
    step: dict[Movable, Any],
    pos_cache: dict[Movable, Any],
) -> None:
    # Mock driver.set to track expected calls
    driver = sim_analyser.driver
    driver.set = AsyncMock(side_effect=fake_status)
    expected_driver_set_calls = [call(r_det.region) for r_det in region_detectors]

    run_engine(analyser_nd_step(all_detectors, step, pos_cache))

    # Our driver instance is shared between each region detector instance.
    # Check that each driver.set was called once with the correct region
    assert driver.set.call_args_list == expected_driver_set_calls


async def test_analyser_nd_step_func_calls_detectors_trigger_and_read_correctly(
    run_engine: RunEngine,
    analyser_nd_step: Callable,
    all_detectors: Sequence[Readable],
    other_detectors: Sequence[Readable],
    region_detectors: Sequence[GenericElectronAnalyserRegionDetector],
    step: dict[Movable, Any],
    pos_cache: dict[Movable, Any],
) -> None:
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

    run_engine(analyser_nd_step(all_detectors, step, pos_cache))

    for r_det in region_detectors:
        r_det.trigger.assert_called_once()  # type: ignore
        r_det.read.assert_called_once()  # type: ignore

    # Check that the other detectors are triggered and read by the number of region
    # detectors.
    for det in other_detectors:
        if isinstance(det, Triggerable):
            assert det.trigger.call_count == len(region_detectors)  # type: ignore
        assert det.read.call_count == len(region_detectors)  # type: ignore


async def test_analyser_nd_step_func_moves_motors_before_detector_trigger(
    run_engine: RunEngine,
    analyser_nd_step: Callable,
    all_detectors: Sequence[Readable],
    step: dict[SimMotor, Any],
    pos_cache: dict[SimMotor, Any],
) -> None:
    shared_mock = MagicMock(side_effect=fake_status)
    for det in all_detectors:
        det.trigger = shared_mock  # type: ignore

    motors = list(step.keys())
    for m in motors:
        m.set = shared_mock

    run_engine(analyser_nd_step(all_detectors, step, pos_cache))

    # Check to see motor.set was called before any r_det.trigger was called.
    for value in step.values():
        assert shared_mock.mock_calls.index(
            call.set(value)
        ) < shared_mock.mock_calls.index(call.trigger())


async def test_analyser_nd_step_func_moves_motors_correctly(
    run_engine: RunEngine,
    analyser_nd_step: Callable,
    all_detectors: Sequence[Readable],
    step: dict[SimMotor, Any],
    pos_cache: dict[SimMotor, Any],
) -> None:
    motors = list(step.keys())

    run_engine(analyser_nd_step(all_detectors, step, pos_cache))

    # Check motors moved to correct position
    for m in motors:
        assert await m.user_readback.get_value() == step[m]
