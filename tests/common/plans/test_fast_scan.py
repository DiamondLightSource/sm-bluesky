from collections.abc import Mapping
from unittest import mock

import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.motors import XYZStage
from numpy import linspace
from ophyd_async.sim import SimPointDetector
from ophyd_async.testing import assert_emitted, get_mock_put

from sm_bluesky.common.plans.fast_scan import fast_scan_1d, fast_scan_grid

# Long enough for multiple asyncio event loop cycles to run so
# all the tasks have a chance to run
A_BIT = 0.001


@pytest.fixture
def det() -> SimPointDetector:
    return SimPointDetector(name="rand", pattern_generator=None, num_channels=1)


async def test_fast_scan_1d_fail_limit_check(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    sim_motor: XYZStage,
    det: SimPointDetector,
) -> None:
    """Testing both high and low limits making sure nothing get run if it is exceeded"""
    with pytest.raises(ValueError):
        run_engine(fast_scan_1d([det], sim_motor.x, 8, 20, 10))

    with pytest.raises(ValueError):
        run_engine(fast_scan_1d([det], sim_motor.x, -208, 0, 10))

    assert 0 == get_mock_put(sim_motor.x.user_setpoint).call_count
    assert 0 == get_mock_put(sim_motor.x.velocity).call_count
    assert_emitted(run_engine_documents, start=2, stop=2)


async def test_fast_scan_1d_success(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    sim_motor: XYZStage,
    det: SimPointDetector,
) -> None:
    run_engine(fast_scan_1d([det], sim_motor.x, 5, -1, 8.0))

    assert 2.78 == await sim_motor.x.velocity.get_value()
    assert 2 == get_mock_put(sim_motor.x.user_setpoint).call_count
    assert 3 == get_mock_put(sim_motor.x.velocity).call_count
    # check speed is set and reset
    assert [
        mock.call(100.0, wait=True),  # prepare set it to max speed
        mock.call(8.0, wait=True),
        mock.call(2.78, wait=True),
    ] == get_mock_put(sim_motor.x.velocity).call_args_list

    """Only 1 event as sim motor motor_done_move is set to True,
      so only 1 loop is ran"""
    assert_emitted(run_engine_documents, start=1, descriptor=1, event=1, stop=1)


async def test_fast_scan_1d_success_without_speed(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    sim_stage_delay: XYZStage,
) -> None:
    run_engine(fast_scan_1d([sim_stage_delay.y], sim_stage_delay.x, 1, 5))

    assert 88.88 == await sim_stage_delay.x.velocity.get_value()
    assert 2 == get_mock_put(sim_stage_delay.x.user_setpoint).call_count
    assert 3 == get_mock_put(sim_stage_delay.x.velocity).call_count
    # check speed is set and reset
    assert [
        mock.call(pytest.approx(0), wait=True),  # SimMotor fast move to start
        mock.call(pytest.approx(88.88), wait=True),
        mock.call(pytest.approx(88.88), wait=True),
    ] == get_mock_put(sim_stage_delay.x.velocity).call_args_list

    """Only 1 event as sim motor motor_done_move is set to True,
      so only 1 loop is ran"""  #
    assert_emitted(run_engine_documents, start=1, descriptor=1, event=mock.ANY, stop=1)


async def test_fast_scan_2d_success(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    sim_motor: XYZStage,
    det: SimPointDetector,
) -> None:
    x_start = 0
    x_end = 2
    num_step = 5
    y_start = -5
    y_end = 5
    speed = 1
    snake_axes = False
    run_engine(
        fast_scan_grid(
            [det],
            sim_motor.x,
            x_start,
            x_end,
            num_step,
            sim_motor.y,
            y_start,
            y_end,
            speed,
            snake_axes=snake_axes,
        ),
    )

    assert 2.78 == await sim_motor.x.velocity.get_value()
    assert num_step == get_mock_put(sim_motor.x.user_setpoint).call_count
    assert 0 == get_mock_put(sim_motor.x.velocity).call_count
    # check step set points
    steps = linspace(x_start, x_end, num_step, endpoint=True)
    for cnt, motor_x in enumerate(
        get_mock_put(sim_motor.x.user_setpoint).call_args_list
    ):
        assert motor_x == mock.call(steps[cnt], wait=True)

    assert 2.88 == await sim_motor.y.velocity.get_value()
    assert num_step * 3 == get_mock_put(sim_motor.y.velocity).call_count
    assert num_step * 2 == get_mock_put(sim_motor.y.user_setpoint).call_count
    # check scan axis set and end point
    for cnt, motor_y in enumerate(
        get_mock_put(sim_motor.y.user_setpoint).call_args_list
    ):
        if cnt % 2 == 0:
            assert motor_y == mock.call(y_start, wait=True)
        else:
            assert motor_y == mock.call(y_end, wait=True)
    """Only 1 event per step as sim motor motor_done_move is set to True,
      so only 1 loop is ran"""
    assert_emitted(run_engine_documents, start=1, descriptor=1, event=num_step, stop=1)


async def test_fast_scan_2d_snake_success(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    sim_motor: XYZStage,
    det: SimPointDetector,
) -> None:
    x_start = 0
    x_end = 2
    num_step = 5
    y_start = -5
    y_end = 4
    speed = 1
    snake_axes = True
    run_engine(
        fast_scan_grid(
            [det],
            sim_motor.x,
            x_start,
            x_end,
            num_step,
            sim_motor.y,
            y_start,
            y_end,
            speed,
            snake_axes=snake_axes,
        ),
    )

    assert 2.78 == await sim_motor.x.velocity.get_value()
    assert num_step == get_mock_put(sim_motor.x.user_setpoint).call_count
    assert 0 == get_mock_put(sim_motor.x.velocity).call_count
    steps = linspace(x_start, x_end, num_step, endpoint=True)
    for cnt, motor_x in enumerate(
        get_mock_put(sim_motor.x.user_setpoint).call_args_list
    ):
        assert motor_x == mock.call(steps[cnt], wait=True)

    assert 2.88 == await sim_motor.y.velocity.get_value()
    assert num_step * 3 == get_mock_put(sim_motor.y.velocity).call_count
    assert num_step * 2 == get_mock_put(sim_motor.y.user_setpoint).call_count
    """ build a list of expected scan motor position"""
    y_position = [y_start]
    for cnt in range(0, num_step):
        if cnt % 2 == 0:
            y_position.extend((y_end, y_end))
        else:
            y_position.extend((y_start, y_start))
    if num_step % 2 == 0:
        y_position.append(y_start)
    else:
        y_position.append(y_end)
    """check them"""
    for cnt, motor_y in enumerate(
        get_mock_put(sim_motor.y.user_setpoint).call_args_list
    ):
        assert motor_y == mock.call(y_position[cnt], wait=True)

    """Only 1 event per step as sim motor motor_done_move is set to True,
      so only 1 loop is ran"""
    assert_emitted(run_engine_documents, start=1, descriptor=1, event=num_step, stop=1)
