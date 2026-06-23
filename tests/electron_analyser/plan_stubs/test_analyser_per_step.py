import asyncio
import re
from collections import defaultdict
from collections.abc import Callable, Sequence
from inspect import iscoroutinefunction
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call

import numpy as np
import pytest
from bluesky import RunEngine
from bluesky import plan_stubs as bps
from bluesky.protocols import Movable, Readable, Triggerable
from dodal.devices.electron_analyser.base import (
    BaseSequence,
    ElectronAnalyserDetector,
    GenericElectronAnalyserDetector,
)
from ophyd_async.core import AsyncStatus, DetectorTrigger, TriggerInfo
from ophyd_async.sim import SimMotor

from sm_bluesky.electron_analyser.plan_stubs import analyser_per_step as aps


@pytest.fixture(params=[0, 1, 2])
def other_detectors(
    request: pytest.FixtureRequest,
) -> list[Readable]:
    return [SimMotor("det" + str(i + 1)) for i in range(request.param)]


@pytest.fixture
def all_detectors(
    sim_analyser: GenericElectronAnalyserDetector,
    other_detectors: Sequence[Readable],
) -> Sequence[Readable]:
    return [sim_analyser] + list(other_detectors)


@pytest.fixture
def step() -> dict[Movable, Any]:
    return {
        SimMotor("motor1"): np.float64(20),
        SimMotor("motor2"): np.float64(10),
    }


@pytest.fixture
def pos_cache() -> dict[Movable, Any]:
    return defaultdict(lambda: 0)


def run_engine_setup_decorator(
    func,
    sim_analyser: GenericElectronAnalyserDetector,
    sequence: BaseSequence,
):
    def wrapper(all_detectors, step, pos_cache):
        yield from bps.prepare(sim_analyser.sequence, sequence)
        default_trigger = TriggerInfo(
            trigger=DetectorTrigger.INTERNAL, number_of_events=1
        )
        yield from bps.prepare(sim_analyser, default_trigger)
        yield from bps.open_run()
        yield from bps.stage_all(*all_detectors)
        yield from func(all_detectors, step, pos_cache)
        yield from bps.unstage_all(*all_detectors)
        yield from bps.close_run()

    return wrapper


@pytest.fixture
def analyser_nd_step(
    sim_analyser: GenericElectronAnalyserDetector,
    sequence: BaseSequence,
) -> Callable:
    return run_engine_setup_decorator(
        aps.analyser_nd_step,
        sim_analyser,
        sequence,
    )


def fake_status(region=None) -> AsyncStatus:
    status = AsyncStatus(asyncio.sleep(0.0))
    return status


async def fake_collect_asset_docs(*args, **kwargs):
    """An empty async generator to mock out ophyd-async asset collection loops."""
    if False:
        yield


def test_analyser_nd_step_func_has_expected_driver_set_calls(
    run_engine: RunEngine,
    analyser_nd_step: Callable,
    all_detectors: Sequence[Readable],
    sim_analyser: GenericElectronAnalyserDetector,
    sequence: BaseSequence,
    step: dict[Movable, Any],
    pos_cache: dict[Movable, Any],
) -> None:
    # Mock driver.set to track expected calls
    controller = sim_analyser._region_logic
    controller.setup_with_region = AsyncMock(side_effect=fake_status)
    expected_driver_set_calls = [
        call(region) for region in sequence.get_enabled_regions()
    ]
    run_engine(analyser_nd_step(all_detectors, step, pos_cache))

    # Check that controller method was called with the number of regions.
    assert controller.setup_with_region.call_args_list == expected_driver_set_calls


async def test_analyser_nd_step_func_calls_detectors_trigger_and_read_correctly(
    run_engine: RunEngine,
    analyser_nd_step: Callable,
    sequence: BaseSequence,
    all_detectors: Sequence[Readable],
    step: dict[Movable, Any],
    pos_cache: dict[Movable, Any],
) -> None:
    for det in all_detectors:
        if isinstance(det, Triggerable):
            det.trigger = MagicMock(side_effect=fake_status)
        mock_read_val = {det.name: {"value": 1, "timestamp": 0.0}}
        mock_desc_val = {det.name: {"source": "mock", "dtype": "number", "shape": []}}

        if iscoroutinefunction(det.read):
            det.read = AsyncMock(return_value=mock_read_val)
        else:
            det.read = MagicMock(return_value=mock_read_val)

        if iscoroutinefunction(det.describe):
            det.describe = AsyncMock(return_value=mock_desc_val)
        else:
            det.describe = MagicMock(return_value=mock_desc_val)

        if hasattr(det, "collect_asset_docs"):
            det.collect_asset_docs = MagicMock(  # type: ignore
                side_effect=fake_collect_asset_docs
            )

    run_engine(analyser_nd_step(all_detectors, step, pos_cache))

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
    call_timeline = []

    def make_set_side_effect(motor_obj):
        def side_effect(val):
            call_timeline.append(("set", motor_obj, val))
            return fake_status()

        return side_effect

    def make_trigger_side_effect(det_obj):
        def side_effect():
            call_timeline.append(("trigger", det_obj))
            return fake_status()

        return side_effect

    for det in all_detectors:
        if hasattr(det, "trigger"):
            det.trigger = MagicMock(side_effect=make_trigger_side_effect(det))  # type: ignore

        mock_read_val = {det.name: {"value": 1, "timestamp": 0.0}}
        mock_desc_val = {det.name: {"source": "mock", "dtype": "number", "shape": []}}

        if iscoroutinefunction(det.read):
            det.read = AsyncMock(return_value=mock_read_val)
        else:
            det.read = MagicMock(return_value=mock_read_val)

        if iscoroutinefunction(det.describe):
            det.describe = AsyncMock(return_value=mock_desc_val)
        else:
            det.describe = MagicMock(return_value=mock_desc_val)

        if hasattr(det, "collect_asset_docs"):
            det.collect_asset_docs = MagicMock(side_effect=fake_collect_asset_docs)  # type: ignore

    motors = list(step.keys())
    for m in motors:
        m.set = MagicMock(side_effect=make_set_side_effect(m))

    run_engine(analyser_nd_step(all_detectors, step, pos_cache))

    # Check to see motor.set was called before any r_det.trigger was called.
    for mot, val in step.items():
        set_index = call_timeline.index(("set", mot, val))
        for det in all_detectors:
            if ("trigger", det) in call_timeline:
                trigger_index = call_timeline.index(("trigger", det))
                assert set_index < trigger_index


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


async def test_analyser_nd_step_raises_error_with_no_analyser(
    run_engine: RunEngine,
    analyser_nd_step: Callable,
    step: dict[SimMotor, Any],
    pos_cache: dict[SimMotor, Any],
):
    with pytest.raises(
        RuntimeError,
        match=re.escape(
            f"Cannot find object from {[]} with type {ElectronAnalyserDetector}"
        ),
    ):
        run_engine(analyser_nd_step([], step, pos_cache))


async def test_analyser_nd_step_raises_error_when_analyser_not_prepared_with_sequence(
    run_engine: RunEngine,
    sim_analyser: GenericElectronAnalyserDetector,
    step: dict[SimMotor, Any],
    pos_cache: dict[SimMotor, Any],
):
    with pytest.raises(
        RuntimeError,
        match=re.escape(
            f"Electron analyser {sim_analyser.name}.sequence is None. It must be "
            "configured using prepare plan stub."
        ),
    ):
        run_engine(aps.analyser_nd_step([sim_analyser], step, pos_cache))  # type: ignore
