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
from dodal.devices.electron_analyser.base import GenericElectronAnalyserDetector
from ophyd_async.core import AsyncStatus
from ophyd_async.sim import SimMotor

from sm_bluesky.electron_analyser.plan_stubs import analyser_per_step as aps


@pytest.fixture
async def analyser_with_sequence(
    sim_analyser: GenericElectronAnalyserDetector, sequence_file: str
) -> GenericElectronAnalyserDetector:
    await sim_analyser.sequence_loader.set(sequence_file)
    assert sim_analyser.sequence_loader.sequence is not None
    return sim_analyser


@pytest.fixture
def number_of_regions(analyser_with_sequence: GenericElectronAnalyserDetector) -> float:
    sequence = analyser_with_sequence.sequence_loader.sequence
    assert sequence is not None
    return len(sequence.get_enabled_regions())


@pytest.fixture(params=[0, 1, 2])
def other_detectors(
    request: pytest.FixtureRequest,
) -> list[Readable]:
    return [SimMotor("det" + str(i + 1)) for i in range(request.param)]


@pytest.fixture
def all_detectors(
    analyser_with_sequence: GenericElectronAnalyserDetector,
    other_detectors: Sequence[Readable],
) -> Sequence[Readable]:
    return [analyser_with_sequence] + list(other_detectors)


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


def fake_status(region=None) -> AsyncStatus:
    status = AsyncStatus(asyncio.sleep(0.0))
    return status


def test_analyser_nd_step_func_has_expected_driver_set_calls(
    run_engine: RunEngine,
    analyser_nd_step: Callable,
    all_detectors: Sequence[Readable],
    sim_analyser: GenericElectronAnalyserDetector,
    step: dict[Movable, Any],
    pos_cache: dict[Movable, Any],
) -> None:
    # Mock driver.set to track expected calls
    controller = sim_analyser._controller
    controller.setup_with_region = AsyncMock(side_effect=fake_status)
    sequence = sim_analyser.sequence_loader.sequence
    assert sequence is not None
    expected_driver_set_calls = [
        call(region) for region in sequence.get_enabled_regions()
    ]

    run_engine(analyser_nd_step(all_detectors, step, pos_cache))

    # Check that controller method was called with the number of regions.
    assert controller.setup_with_region.call_args_list == expected_driver_set_calls


async def test_analyser_nd_step_func_calls_detectors_trigger_and_read_correctly(
    run_engine: RunEngine,
    analyser_nd_step: Callable,
    sim_analyser: GenericElectronAnalyserDetector,
    all_detectors: Sequence[Readable],
    step: dict[Movable, Any],
    pos_cache: dict[Movable, Any],
) -> None:
    for det in all_detectors:
        if isinstance(det, Triggerable):
            det.trigger = MagicMock(side_effect=fake_status)

        # Check if detector needs to be mocked with async or not.
        if asyncio.iscoroutinefunction(det.read):
            det.read = AsyncMock(return_value=await det.read())
        else:
            det.read = MagicMock(return_value=det.read())

    run_engine(analyser_nd_step(all_detectors, step, pos_cache))

    sequence = sim_analyser.sequence_loader.sequence
    assert sequence is not None
    n_regions = len(sequence.get_enabled_regions())

    # Check that alldetectors are triggered and read by the number of regions.
    for det in all_detectors:
        if isinstance(det, Triggerable):
            assert det.trigger.call_count == n_regions  # type: ignore
        assert det.read.call_count == n_regions  # type: ignore


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
