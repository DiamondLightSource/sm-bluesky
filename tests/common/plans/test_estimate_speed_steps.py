import pytest

from sm_bluesky.common.plans.grid_scan import estimate_speed_steps


def test_estimate_speed_steps_with_explicit_step_size():
    # Arrange
    plan_time = 10.0
    deadtime = 0.2
    step_start = 0.0
    step_end = 2.0
    step_size = 0.5
    step_acceleration = 0.1
    step_speed = 1.0
    scan_start = -1.0
    scan_end = 1.0
    scan_acceleration = 0.1
    scan_speed = 1.0
    scan_max_vel = 5.0
    snake_axes = True
    correction = 1

    ideal_velocity, ideal_step_size = estimate_speed_steps(
        plan_time=plan_time,
        deadtime=deadtime,
        step_start=step_start,
        step_end=step_end,
        step_size=step_size,
        step_acceleration=step_acceleration,
        step_speed=step_speed,
        scan_start=scan_start,
        scan_end=scan_end,
        scan_acceleration=scan_acceleration,
        scan_speed=scan_speed,
        scan_max_vel=scan_max_vel,
        snake_axes=snake_axes,
        correction=correction,
    )

    assert ideal_step_size == pytest.approx(0.5)

    # Velocity calculation: 2.0 / ((2.0 / 0.5) * 0.2 + 0.1 * 2) = 2.0
    assert ideal_velocity == pytest.approx(2.0)


def test_estimate_speed_steps_no_step_size_calculates_exact_grid():
    # Arrange
    plan_time = 100.0
    deadtime = 0.5
    step_start = 0.0
    step_end = 4.0
    step_size = None
    step_acceleration = 0.2
    step_speed = 2.0
    scan_start = -2.0
    scan_end = 2.0
    scan_acceleration = 0.2
    scan_speed = 2.0
    scan_max_vel = 10.0
    snake_axes = True
    correction = 1

    # Act
    ideal_velocity, ideal_step_size = estimate_speed_steps(
        plan_time=plan_time,
        deadtime=deadtime,
        step_start=step_start,
        step_end=step_end,
        step_size=step_size,
        step_acceleration=step_acceleration,
        step_speed=step_speed,
        scan_start=scan_start,
        scan_end=scan_end,
        scan_acceleration=scan_acceleration,
        scan_speed=scan_speed,
        scan_max_vel=scan_max_vel,
        snake_axes=snake_axes,
        correction=correction,
    )

    # 4.0/ 13 step
    assert ideal_step_size == pytest.approx(4.0 / 13.0)

    # 4.0 / (13 measurements * 0.5s deadtime + 0.4s turnaround overhead)
    assert ideal_velocity == pytest.approx(4.0 / 6.9)


def test_estimate_speed_steps_low_point_count_caps_velocity():
    plan_time = 10.0
    deadtime = 5.0
    step_start, step_end = 0.0, 1.0
    scan_start, scan_end = 0.0, 1.0
    scan_max_vel = 42.0

    # Act
    ideal_velocity, _ = estimate_speed_steps(
        plan_time=plan_time,
        deadtime=deadtime,
        step_start=step_start,
        step_end=step_end,
        step_size=None,
        step_acceleration=0.1,
        step_speed=1.0,
        scan_start=scan_start,
        scan_end=scan_end,
        scan_acceleration=0.1,
        scan_speed=1.0,
        scan_max_vel=scan_max_vel,
        snake_axes=True,
        correction=1,
    )

    assert ideal_velocity == scan_max_vel


def test_estimate_speed_steps_insufficient_time_raises_error():
    plan_time = 0.1
    deadtime = 0.1
    step_acceleration = 5.0
    scan_acceleration = 5.0

    # Act & Assert
    with pytest.raises(ValueError, match="Plan execution window is too short"):
        estimate_speed_steps(
            plan_time=plan_time,
            deadtime=deadtime,
            step_start=0.0,
            step_end=10.0,
            step_size=None,
            step_acceleration=step_acceleration,
            step_speed=1.0,
            scan_start=0.0,
            scan_end=10.0,
            scan_acceleration=scan_acceleration,
            scan_speed=1.0,
            scan_max_vel=10.0,
            snake_axes=True,
            correction=1,
        )


def test_estimate_speed_steps_non_snake_axes_converges():
    plan_time = 100.0
    deadtime = 0.2

    ideal_velocity, ideal_step_size = estimate_speed_steps(
        plan_time=plan_time,
        deadtime=deadtime,
        step_start=0.0,
        step_end=4.0,
        step_size=None,
        step_acceleration=0.1,
        step_speed=2.0,
        scan_start=0.0,
        scan_end=4.0,
        scan_acceleration=0.1,
        scan_speed=2.0,
        scan_max_vel=10.0,
        snake_axes=False,
        correction=1,
    )

    assert ideal_velocity > 0
    assert ideal_step_size > 0
