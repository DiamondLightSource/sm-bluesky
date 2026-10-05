from collections import defaultdict
from collections.abc import Callable, Sequence
from inspect import iscoroutinefunction
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call

import numpy as np
import pytest
from bluesky import RunEngine
from bluesky import plan_stubs as bps
from bluesky.plans import PerStepND
from bluesky.protocols import Movable, Readable, Triggerable
from dodal.devices.electron_analyser.base import BaseSequence, ElectronAnalyserDetector
from dodal.devices.fast_shutter import GenericFastShutter
from ophyd_async.sim import SimMotor

from sm_bluesky.electron_analyser.plan_stubs import analyser_per_step as aps


@pytest.fixture(params=[0, 1, 2])
def other_detectors(
    request: pytest.FixtureRequest,
) -> list[Readable]:
    return [SimMotor("det" + str(i + 1)) for i in range(request.param)]


@pytest.fixture
def all_detectors(
    sim_analyser: ElectronAnalyserDetector,
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


def run_engine_setup_decorator(func: PerStepND) -> Callable:
    def wrapper(all_detectors, step, pos_cache, take_reading=None):
        yield from bps.open_run()
        yield from bps.stage_all(*all_detectors)

        try:
            yield from func(all_detectors, step, pos_cache, take_reading)
        finally:
            yield from bps.unstage_all(*all_detectors)
            yield from bps.close_run()

    return wrapper


@pytest.fixture
def analyser_nd_step(
    sim_analyser: ElectronAnalyserDetector,
    sequence: BaseSequence,
) -> Callable:
    return run_engine_setup_decorator(
        aps.make_analyser_per_step(
            sim_analyser,
            sequence,
            [],
            close_shutter_per_region=False,
            shutter=None,
        )
    )


def test_analyser_nd_step_func_has_expected_driver_set_calls(
    run_engine: RunEngine,
    analyser_nd_step: Callable,
    all_detectors: Sequence[Readable],
    sim_analyser: ElectronAnalyserDetector,
    sequence: BaseSequence,
    step: dict[Movable, Any],
    pos_cache: dict[Movable, Any],
) -> None:
    # Mock driver.set to track expected calls
    region_logic = sim_analyser._region_logic
    original_setup_with_region = region_logic.setup_with_region
    region_logic.setup_with_region = AsyncMock(side_effect=original_setup_with_region)
    expected_driver_set_calls = [
        call(region) for region in sequence.get_enabled_regions()
    ]
    run_engine(analyser_nd_step(all_detectors, step, pos_cache, None))

    # Check that region_logic method was called with the number of regions.
    assert region_logic.setup_with_region.call_args_list == expected_driver_set_calls


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
            original_trigger = det.trigger
            det.trigger = MagicMock(side_effect=original_trigger)

        # Check if detector needs to be mocked with async or not.
        original_read = det.read
        if iscoroutinefunction(det.read):
            det.read = AsyncMock(wraps=original_read)
        else:
            det.read = MagicMock(wraps=original_read)

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

    call_order = []

    # Spy on motor moves
    for motor in step:
        original_set = motor.set

        def wrapped_set(*args, _original=original_set, **kwargs):
            call_order.append("set")
            return _original(*args, **kwargs)

        motor.set = wrapped_set

    # Spy on detector triggers
    for det in all_detectors:
        if isinstance(det, Triggerable):
            original_trigger = det.trigger

            def wrapped_trigger(*args, _original=original_trigger, **kwargs):
                call_order.append("trigger")
                return _original(*args, **kwargs)

            det.trigger = wrapped_trigger

    run_engine(analyser_nd_step(all_detectors, step, pos_cache))

    # Check to see motor.set was called before any det.trigger was called.
    assert call_order.index("trigger") > max(
        i for i, op in enumerate(call_order) if op == "set"
    )


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


@pytest.mark.parametrize(
    "callable", [aps.make_analyser_per_step, aps.make_analyser_per_shot]
)
def test_make_analyser_per_step_requires_shutter_when_closing_per_region(
    sim_analyser: ElectronAnalyserDetector,
    sequence: BaseSequence,
    all_detectors: Sequence[Readable],
    callable: Callable,
) -> None:
    with pytest.raises(
        ValueError,
        match="close_shutter_per_region=True requires a shutter to be provided.",
    ):
        callable(
            sim_analyser,
            sequence,
            all_detectors,
            close_shutter_per_region=True,
            shutter=None,
        )


@pytest.mark.parametrize(
    "callable", [aps.make_analyser_per_step, aps.make_analyser_per_shot]
)
def test_make_analyser_per_step_requires_enabled_regions(
    sim_analyser: ElectronAnalyserDetector,
    all_detectors: Sequence[Readable],
    callable: Callable,
) -> None:
    with pytest.raises(ValueError, match="Sequence has zero enabled regions."):
        callable(
            sim_analyser,
            BaseSequence(),
            all_detectors,
            close_shutter_per_region=False,
            shutter=None,
        )


@pytest.mark.parametrize(
    "close_shutter_per_region, expected_shutter_calls",
    [
        (True, [call(True), call(False)]),
        (False, [call(True)]),
    ],
)
def test_analyser_nd_step_operates_shutter_correctly(
    run_engine: RunEngine,
    sim_analyser: ElectronAnalyserDetector,
    sequence: BaseSequence,
    all_detectors: Sequence[Readable],
    step: dict[Movable, Any],
    pos_cache: dict[Movable, Any],
    shutter: GenericFastShutter,
    close_shutter_per_region: bool,
    expected_shutter_calls: list,
) -> None:
    analyser_nd_step = run_engine_setup_decorator(
        aps.make_analyser_per_step(
            sim_analyser,
            sequence,
            [],
            close_shutter_per_region=close_shutter_per_region,
            shutter=shutter,
        )
    )
    original_set = shutter.open.set
    shutter.open.set = MagicMock(wraps=original_set)

    run_engine(analyser_nd_step(all_detectors, step, pos_cache, None))
    n_regions = len(sequence.get_enabled_regions())
    assert shutter.open.set.call_args_list == expected_shutter_calls * n_regions


def test_optional_close_shutter_plan(
    run_engine: RunEngine, shutter: GenericFastShutter
):
    original_set = shutter.open.set
    shutter.open.set = MagicMock(wraps=original_set)
    run_engine(aps.close_shutter(shutter))
    shutter.open.set.assert_called_once_with(False)

    # Test providing no shutter doesn't do anything.
    run_engine(aps.close_shutter())
    shutter.open.set.assert_called_once()


@pytest.mark.parametrize(
    "callable", [aps.make_analyser_per_step, aps.make_analyser_per_shot]
)
def test_make_analyserscan_plan_duplicate_analyser(
    sim_analyser: ElectronAnalyserDetector, sequence: BaseSequence, callable: Callable
) -> None:
    with pytest.raises(
        ValueError,
        match=f"{sim_analyser.name} is provided as analyser argument and also in the "
        "detectors list argument. Please remove it from detector list.",
    ):
        callable(
            sim_analyser,
            sequence,
            detectors=[sim_analyser],
            close_shutter_per_region=False,
            shutter=None,
        )
