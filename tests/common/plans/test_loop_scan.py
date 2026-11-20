from collections.abc import Mapping, Sequence

import pytest
from bluesky.run_engine import RunEngine
from ophyd_async.testing import assert_emitted

from sm_bluesky.common.plans import loop_step_scan
from sm_bluesky.common.plans.loop_scan import _generate_loop_positions
from sm_bluesky.common.sim_devices import SimDetector, SimStage


@pytest.mark.parametrize(
    "start, stop, step_size, mirror, expected",
    [
        (
            0.0,
            3.0,
            2.0,
            True,
            [0.0, 1.5, 3.0, 1.5, 0.0],
        ),
        (
            3.0,
            0.0,
            2.0,
            True,
            [3.0, 1.5, 0.0, 1.5, 3.0],
        ),
        (
            1.0,
            0.0,
            5.0,
            True,
            [1.0, 0.0, 1.0],
        ),
        (
            0.0,
            4.0,
            -1.0,
            True,
            [0.0, 1.0, 2.0, 3.0, 4.0, 3.0, 2.0, 1.0, 0.0],
        ),
        (
            2.5,
            2.5,
            1.0,
            True,
            [2.5],
        ),
        (
            [-2.0, -1.0, 1.0],
            [-1.0, 1.0, 2.0],
            [1.0, 0.5, 1.0],
            True,
            [-2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0, 1.0, 0.5, 0.0, -0.5, -1.0, -2.0],
        ),
        (
            0.0,
            4.0,
            1.0,
            False,
            [0.0, 1.0, 2.0, 3.0, 4.0],
        ),
        (
            [0.0, 2.0],
            [2.0, 0.0],
            [0.5, 1.0],
            False,
            [0.0, 0.5, 1.0, 1.5, 2.0, 1.0, 0.0],
        ),
        (
            [0.0, 2.0, -2.0],
            [2.0, -2.0, 2.0],
            1.0,
            False,
            [0.0, 1.0, 2.0, 1.0, 0.0, -1.0, -2.0, -1.0, 0.0, 1.0, 2.0],
        ),
        (
            [0.0, 5.0],
            [2.0, 7.0],
            [1.0, 1.0],
            False,
            [0.0, 1.0, 2.0, 5.0, 6.0, 7.0],
        ),
    ],
)
def test_generate_loop_positions(
    start: float | Sequence[float],
    stop: float | Sequence[float],
    step_size: float | Sequence[float],
    mirror: bool,
    expected: list[float],
) -> None:
    positions = _generate_loop_positions(start, stop, step_size, mirror=mirror)
    assert positions == pytest.approx(expected)
    if mirror:
        assert positions == list(reversed(positions))


@pytest.mark.parametrize(
    "start, stop, step_size, match",
    [
        (0.0, 1.0, 0.0, "step_size must not be zero"),
        (
            [0.0, 1.0],
            [1.0, 2.0],
            [0.5, 0.0],
            "step_size must not be zero",
        ),
        (
            [],
            [],
            [],
            "start and stop must not be empty",
        ),
        (
            [0.0, 1.0],
            [1.0],
            [0.5, 0.5],
            "start and stop must not be empty and have the same length",
        ),
        (
            [0.0, 1.0],
            [1.0, 2.0],
            [0.5],
            "step_size must be a single value or match the number of regions",
        ),
    ],
)
def test_generate_loop_positions_invalid(
    start: float | Sequence[float],
    stop: float | Sequence[float],
    step_size: float | Sequence[float],
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        _generate_loop_positions(start, stop, step_size)


@pytest.mark.parametrize(
    "start, stop, step_size, mirror, expected_positions",
    [
        (
            0.0,
            0.3,
            0.1,
            True,
            [0.0, 0.1, 0.2, 0.3, 0.2, 0.1, 0.0],
        ),
        (
            2.0,
            2.0,
            0.5,
            True,
            [2.0],
        ),
        (
            [-2.0, -1.0, 1.0],
            [-1.0, 1.0, 2.0],
            [1.0, 0.5, 1.0],
            True,
            [-2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0, 1.0, 0.5, 0.0, -0.5, -1.0, -2.0],
        ),
        (
            [0.0, 2.0],
            [2.0, 0.0],
            [0.5, 1.0],
            False,
            [0.0, 0.5, 1.0, 1.5, 2.0, 1.0, 0.0],
        ),
    ],
)
async def test_loop_step_scan_forward_and_return_single_run(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    sim_stage_step: SimStage,
    fake_detector: SimDetector,
    start: float | Sequence[float],
    stop: float | Sequence[float],
    step_size: float | Sequence[float],
    mirror: bool,
    expected_positions: list[float],
) -> None:
    run_engine(
        loop_step_scan(
            [fake_detector],
            sim_stage_step.x,
            start,
            stop,
            step_size,
            mirror=mirror,
        )
    )

    assert_emitted(
        run_engine_documents,
        start=1,
        descriptor=1,
        event=len(expected_positions),
        stop=1,
    )
    assert run_engine_documents["start"][0]["plan_name"] == "loop_step_scan"
    events = run_engine_documents["event"]
    positions = [event["data"][sim_stage_step.x.name] for event in events]
    assert positions == pytest.approx(expected_positions)
    if mirror:
        assert positions == pytest.approx(list(reversed(positions)))
    assert all(f"{fake_detector.name}-value" in event["data"] for event in events)
    assert await sim_stage_step.x.user_readback.get_value() == pytest.approx(
        expected_positions[-1]
    )
