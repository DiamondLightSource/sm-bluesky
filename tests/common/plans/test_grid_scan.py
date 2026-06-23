from collections.abc import Mapping
from unittest.mock import ANY

import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.motors import XYZStage
from dodal.devices.single_trigger_detector import SingleTriggerDetector
from numpy import random
from ophyd_async.core import set_mock_value
from ophyd_async.epics.adandor import AndorDetector
from ophyd_async.testing import assert_emitted

from sm_bluesky.common.math_functions import step_size_to_step_num
from sm_bluesky.common.plans.grid_scan import (
    estimate_speed_steps,
    grid_fast_scan,
    grid_step_scan,
)
from sm_bluesky.common.sim_devices import SimStage


async def test_grid_fast_zero_velocity_fail(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    andor2: AndorDetector,
    sim_motor: XYZStage,
) -> None:
    plan_time = 10
    count_time = 0.2
    step_size = 0.0
    step_start = -2
    step_end = 3
    with pytest.raises(ValueError):
        run_engine(
            grid_fast_scan(
                dets=[andor2],
                count_time=count_time,
                step_motor=sim_motor.x,
                step_start=step_start,
                step_end=step_end,
                scan_motor=sim_motor.y,
                scan_start=1,
                scan_end=2,
                plan_time=plan_time,
                step_size=step_size,
            ),
        )
    # should do nothingdocs = defaultdict(list)
    assert_emitted(run_engine_documents)


async def test_grid_fast(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    andor2: AndorDetector,
    sim_motor: XYZStage,
) -> None:
    plan_time = 50
    count_time = 0.1
    step_size = 0.1
    step_start = -2
    step_end = 3
    num_of_step = step_size_to_step_num(step_start, step_end, step_size)

    run_engine(
        grid_fast_scan(
            dets=[sim_motor.z, andor2],
            count_time=count_time,
            step_motor=sim_motor.x,
            step_start=step_start,
            step_end=step_end,
            scan_motor=sim_motor.y,
            scan_start=1,
            scan_end=2,
            plan_time=plan_time,
            step_size=step_size,
            home=True,
        ),
    )
    assert_emitted(
        run_engine_documents,
        start=1,
        descriptor=1,
        stream_resource=1,
        stream_datum=num_of_step,
        event=num_of_step,
        stop=1,
    )


async def test_grid_fast_with_too_little_time_grid_become_1d(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    andor2: AndorDetector,
    sim_motor: XYZStage,
) -> None:
    plan_time = 1.5
    count_time = 0.1
    step_start = 2.9
    step_end = 3

    run_engine(
        grid_fast_scan(
            dets=[sim_motor.z, andor2],
            count_time=count_time,
            step_motor=sim_motor.x,
            step_start=step_start,
            step_end=step_end,
            scan_motor=sim_motor.y,
            scan_start=-5,
            scan_end=5,
            plan_time=plan_time,
            home=True,
        ),
    )
    assert_emitted(
        run_engine_documents,
        start=1,
        descriptor=1,
        stream_resource=1,
        stream_datum=1,
        event=1,
        stop=1,
    )


async def test_grid_fast_with_too_little_time_grid_cannot_have_any_points(
    run_engine: RunEngine,
    andor2: AndorDetector,
    sim_motor: XYZStage,
) -> None:
    plan_time = 10
    count_time = 0.1
    step_start = 2.0
    step_end = 4
    set_mock_value(sim_motor.x.velocity, 10)
    set_mock_value(sim_motor.x.acceleration_time, 0)
    set_mock_value(sim_motor.y.velocity, 10)
    set_mock_value(sim_motor.y.acceleration_time, 0)
    with pytest.raises(ValueError):
        run_engine(
            grid_fast_scan(
                dets=[sim_motor.z, andor2],
                count_time=count_time,
                step_motor=sim_motor.x,
                step_start=step_start,
                step_end=step_end,
                scan_motor=sim_motor.y,
                scan_start=-5,
                scan_end=5,
                plan_time=plan_time,
                snake_axes=False,
                home=True,
            ),
        )


async def test_grid_fast_with_speed_capped(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    andor2: AndorDetector,
    sim_motor: XYZStage,
) -> None:
    plan_time = 10
    count_time = 0.0
    step_size = 0.2
    step_start = -2
    step_end = 2
    num_of_step = step_size_to_step_num(step_start, step_end, step_size)
    set_mock_value(
        sim_motor.y.max_velocity, 1
    )  # running at half the speed that required
    run_engine(
        grid_fast_scan(
            dets=[andor2],
            count_time=count_time,
            step_motor=sim_motor.x,
            step_start=step_start,
            step_end=step_end,
            scan_motor=sim_motor.y,
            scan_start=1,
            scan_end=2,
            plan_time=plan_time,
            step_size=step_size,
            home=True,
        ),
    )
    assert_emitted(
        run_engine_documents,
        start=1,
        descriptor=1,
        stream_resource=1,
        stream_datum=int(num_of_step * 0.5),
        event=int(num_of_step * 0.5),
        stop=1,
    )


async def test_grid_fast_unknown_step_snake(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    andor2: AndorDetector,
    sim_motor: XYZStage,
) -> None:
    rng = random.default_rng()
    number_of_point = rng.integers(low=5, high=20)

    step_motor_speed = rng.uniform(low=1.5, high=10)
    scan_motor_speed = rng.uniform(low=1.5, high=10)
    step_acc = step_motor_speed * rng.uniform(low=0.01, high=0.1)
    scan_acc = scan_motor_speed * rng.uniform(low=0.01, high=0.1)
    step_start = rng.uniform(low=-1, high=1.5)
    step_end = 5
    scan_start = rng.uniform(low=-1, high=2)
    scan_end = 3
    count_time = rng.uniform(low=0.1, high=1)
    det_dead_time = 0.1
    deadtime = count_time + det_dead_time + step_acc
    step_range = abs(step_start - step_end)
    scan_range = abs(scan_start - scan_end)
    set_mock_value(sim_motor.x.velocity, step_motor_speed)
    set_mock_value(sim_motor.x.acceleration_time, step_acc)
    set_mock_value(sim_motor.y.velocity, scan_motor_speed)
    set_mock_value(sim_motor.y.acceleration_time, scan_acc)
    set_mock_value(sim_motor.x.high_limit_travel, 88)
    set_mock_value(sim_motor.x.low_limit_travel, -88)

    set_mock_value(sim_motor.y.high_limit_travel, 88)
    set_mock_value(sim_motor.y.low_limit_travel, -88)
    plan_time = (
        number_of_point**2 * (deadtime)
        + step_range / step_motor_speed
        + (number_of_point - 1) * (scan_range / scan_motor_speed + scan_acc * 2)
    ) + step_acc * number_of_point
    run_engine(
        grid_fast_scan(
            dets=[andor2],
            count_time=count_time,
            step_motor=sim_motor.x,
            step_start=step_start,
            step_end=step_end,
            scan_motor=sim_motor.y,
            scan_start=scan_start,
            scan_end=scan_end,
            plan_time=plan_time,
            home=True,
        ),
    )
    scan_max_vel = await sim_motor.y.max_velocity.get_value()
    deadtime = andor2._trigger_logic.get_deadtime(count_time)  # type: ignore
    _, ideal_step_size = estimate_speed_steps(
        plan_time=plan_time,
        deadtime=deadtime,
        step_start=step_start,
        step_end=step_end,
        step_size=None,
        step_acceleration=step_acc,
        step_speed=step_motor_speed,
        scan_start=scan_start,
        scan_end=scan_end,
        scan_acceleration=scan_acc,
        scan_speed=scan_motor_speed,
        scan_max_vel=scan_max_vel,
        snake_axes=True,
        correction=1.0,
    )

    expected_steps = step_size_to_step_num(step_start, step_end, ideal_step_size)
    assert run_engine_documents["event"].__len__() == pytest.approx(
        expected_steps, rel=1
    )


async def test_grid_fast_unknown_step_no_snake(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    andor2: AndorDetector,
    sim_motor: XYZStage,
) -> None:
    step_motor_speed = 1
    scan_motor_speed = 2
    step_acc = 0.1
    scan_acc = 0.1
    step_start = 0
    step_end = 2
    scan_start = -1
    scan_end = 1
    count_time = 0.1
    det_dead_time = 0.1
    scan_range = abs(scan_start - scan_end)
    step_range = abs(step_start - step_end)
    set_mock_value(sim_motor.x.velocity, step_motor_speed)
    set_mock_value(sim_motor.x.acceleration_time, 0.1)
    set_mock_value(sim_motor.x.high_limit_travel, 88)
    set_mock_value(sim_motor.x.low_limit_travel, -88)

    set_mock_value(sim_motor.y.velocity, scan_motor_speed)
    set_mock_value(sim_motor.y.acceleration_time, 0.1)
    set_mock_value(sim_motor.y.high_limit_travel, 88)
    set_mock_value(sim_motor.y.low_limit_travel, -88)
    rng = random.default_rng()

    number_of_point = rng.integers(low=5, high=25)

    plan_time = (
        number_of_point**2 * (count_time + det_dead_time)
        + number_of_point * (step_acc * 2 + scan_acc * 2)
        + step_range / step_motor_speed
        + (number_of_point) * (scan_range / scan_motor_speed + scan_acc * 2)
        + 10
    )
    run_engine(
        grid_fast_scan(
            dets=[andor2],
            count_time=count_time,
            step_motor=sim_motor.x,
            step_start=step_start,
            step_end=step_end,
            scan_motor=sim_motor.y,
            scan_start=scan_start,
            scan_end=scan_end,
            plan_time=plan_time,
            snake_axes=False,
            home=True,
        ),
    )

    scan_max_vel = await sim_motor.y.max_velocity.get_value()
    deadtime = andor2._trigger_logic.get_deadtime(count_time)  # type: ignore
    ideal_velocity, ideal_step_size = estimate_speed_steps(
        plan_time=plan_time,
        deadtime=deadtime,
        step_start=step_start,
        step_end=step_end,
        step_size=None,
        step_acceleration=step_acc,
        step_speed=step_motor_speed,
        scan_start=scan_start,
        scan_end=scan_end,
        scan_acceleration=scan_acc,
        scan_speed=scan_motor_speed,
        scan_max_vel=scan_max_vel,
        snake_axes=False,
        correction=1,
    )

    expected_steps = step_size_to_step_num(step_start, step_end, ideal_step_size)

    assert run_engine_documents["event"].__len__() == pytest.approx(
        expected_steps, abs=1
    )


async def test_grid_fast_unknown_step_snake_with_point_correction(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    andor2: AndorDetector,
    sim_motor: XYZStage,
) -> None:
    rng = random.default_rng()
    point_correction = rng.uniform(low=0.2, high=1)
    step_motor_speed = 10
    scan_motor_speed = 10
    step_acc = 0.1
    scan_acc = 0.1
    step_start = rng.uniform(low=-4, high=1)
    step_end = 5
    scan_start = -1
    scan_end = 1
    count_time = 0.1

    set_mock_value(sim_motor.x.velocity, step_motor_speed)
    set_mock_value(sim_motor.x.low_limit_travel, -10)
    set_mock_value(sim_motor.x.high_limit_travel, 10)
    set_mock_value(sim_motor.x.acceleration_time, step_acc)
    set_mock_value(sim_motor.y.velocity, scan_motor_speed)
    set_mock_value(sim_motor.y.low_limit_travel, -10)
    set_mock_value(sim_motor.y.high_limit_travel, 10)
    set_mock_value(sim_motor.y.acceleration_time, scan_acc)

    plan_time = 100  # plan time to exercise point correction behavior

    run_engine(
        grid_fast_scan(
            dets=[andor2],
            count_time=count_time,
            step_motor=sim_motor.x,
            step_start=step_start,
            step_end=step_end,
            scan_motor=sim_motor.y,
            scan_start=scan_start,
            scan_end=scan_end,
            plan_time=plan_time,
            point_correction=point_correction,
            home=True,
        ),
    )

    deadtime = andor2._trigger_logic.get_deadtime(count_time)  # type: ignore
    scan_max_vel = await sim_motor.y.max_velocity.get_value()
    _, ideal_step_size = estimate_speed_steps(
        plan_time=plan_time,
        deadtime=deadtime,
        step_start=step_start,
        step_end=step_end,
        step_size=None,
        step_acceleration=step_acc,
        step_speed=step_motor_speed,
        scan_start=scan_start,
        scan_end=scan_end,
        scan_acceleration=scan_acc,
        scan_speed=scan_motor_speed,
        scan_max_vel=scan_max_vel,
        snake_axes=True,
        correction=point_correction,
    )

    expected_steps = step_size_to_step_num(step_start, step_end, ideal_step_size)

    # +- one data point due to rounding
    assert run_engine_documents["event"].__len__() == pytest.approx(
        expected_steps, abs=1
    )


async def test_grid_step_with_home(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    sim_stage_step: SimStage,
    andor2: AndorDetector,
) -> None:
    await sim_stage_step.x.set(-1)
    await sim_stage_step.y.set(-2)

    run_engine(
        grid_step_scan(
            dets=[andor2],
            count_time=0.2,
            x_step_motor=sim_stage_step.x,  # type: ignore
            x_step_start=0,
            x_step_end=2,
            x_step_size=0.2,
            y_step_motor=sim_stage_step.y,  # type: ignore
            y_step_start=-1,
            y_step_end=1,
            y_step_size=0.25,
            home=True,
            snake=True,
        ),
    )

    assert_emitted(
        run_engine_documents,
        start=1,
        descriptor=1,
        stream_resource=1,
        stream_datum=99,
        event=99,
        stop=1,
    )
    assert -1 == await sim_stage_step.x.user_readback.get_value()
    assert -2 == await sim_stage_step.y.user_readback.get_value()


async def test_grid_step_without_home_with_readable(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    sim_stage_step: SimStage,
) -> None:
    await sim_stage_step.x.set(-1)
    await sim_stage_step.y.set(-2)
    y_step_end = 1
    x_step_end = 2
    run_engine(
        grid_step_scan(
            dets=[sim_stage_step.z],
            count_time=0.2,
            x_step_motor=sim_stage_step.x,  # type: ignore
            x_step_start=0,
            x_step_end=x_step_end,
            x_step_size=0.2,
            y_step_motor=sim_stage_step.y,  # type: ignore
            y_step_start=-1,
            y_step_end=y_step_end,
            y_step_size=0.25,
            home=False,
            snake=False,
        ),
    )
    assert_emitted(run_engine_documents, start=1, descriptor=1, event=99, stop=1)
    assert x_step_end == await sim_stage_step.x.user_readback.get_value()
    assert y_step_end == await sim_stage_step.y.user_readback.get_value()


async def test_grid_fast_sim_flyable_motor_with_andor_point(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    andor2_point: SingleTriggerDetector,
    sim_stage_delay: XYZStage,
) -> None:
    plan_time = 0.5
    count_time = 0.01
    step_size = 0.2
    step_start = -0.5
    step_end = 0.5
    run_engine(
        grid_fast_scan(
            dets=[andor2_point],
            count_time=count_time,
            step_motor=sim_stage_delay.x,
            step_start=step_start,
            step_end=step_end,
            scan_motor=sim_stage_delay.y,
            scan_start=1,
            scan_end=2,
            plan_time=plan_time,
            step_size=step_size,
            snake_axes=True,
            home=False,
        ),
    )
    assert_emitted(run_engine_documents, start=1, descriptor=1, event=ANY, stop=1)


async def test_grid_fast_sim_flyable_motor(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    andor2: AndorDetector,
    sim_stage_delay: XYZStage,
) -> None:
    plan_time = 0.5
    count_time = 0.01
    step_size = 0.2
    step_start = -0.5
    step_end = 0.5
    run_engine(
        grid_fast_scan(
            dets=[andor2],
            count_time=count_time,
            step_motor=sim_stage_delay.x,
            step_start=step_start,
            step_end=step_end,
            scan_motor=sim_stage_delay.y,
            scan_start=1,
            scan_end=2,
            plan_time=plan_time,
            step_size=step_size,
            snake_axes=True,
            home=False,
        ),
    )

    assert_emitted(
        run_engine_documents,
        start=1,
        descriptor=1,
        stream_resource=1,
        stream_datum=ANY,
        event=ANY,
        stop=1,
    )
    assert (
        run_engine_documents["event"].__len__()
        == run_engine_documents["stream_datum"].__len__()
    )
