import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.motors import XYZStage
from dodal.devices.slits import Slits
from ophyd_async.core import init_devices
from ophyd_async.epics.motor import Motor
from ophyd_async.testing import callback_on_mock_put, set_mock_value

from sm_bluesky.common.plan_stubs import (
    check_within_limit,
    get_velocity_and_step_size,
    move_motor_with_look_up,
    set_slit_size,
)

fake_motor_look_up = {"5000": 1.8, "1000": 8, "-500": 8.8, "100": 55, "50": -34.3}


def test_check_within_limit(sim_motor_step: XYZStage, RE: RunEngine):
    set_mock_value(sim_motor_step.x.low_limit_travel, -10)
    set_mock_value(sim_motor_step.x.high_limit_travel, 20)

    with pytest.raises(ValueError):
        RE(check_within_limit([-11], sim_motor_step.x))

    with pytest.raises(ValueError):
        RE(check_within_limit([21], sim_motor_step.x))

    RE(check_within_limit([18], sim_motor_step.x))


def test_motor_with_look_up_fail(RE: RunEngine, sim_motor_step: XYZStage):
    size = 400
    with pytest.raises(ValueError) as e:
        RE(
            move_motor_with_look_up(
                sim_motor_step.z, size=size, motor_table=fake_motor_look_up
            )
        )
    assert (
        str(e.value)
        == f"No slit with size={size}. Available slit size: {fake_motor_look_up}"
    )


def test_motor_with_look_up_fail_invalid_table(RE: RunEngine, sim_motor_step: XYZStage):
    bad_motor_look_up = {"5000": 1.8, "1000": 8, "-500": 8.8, "100": "sdsf", "50": 34.3}

    size = 400
    with pytest.raises(ValueError):
        RE(
            move_motor_with_look_up(
                sim_motor_step.z, size=size, motor_table=bad_motor_look_up
            )
        )


@pytest.mark.parametrize(
    "test_input, expected_centre",
    [(5000, 1.8), (-500, 8.8), (50, -34.3)],
)
async def test_motor_with_look_up_move_using_table_success(
    RE: RunEngine, sim_motor_step: XYZStage, test_input, expected_centre
):
    RE(
        move_motor_with_look_up(
            sim_motor_step.z, size=test_input, motor_table=fake_motor_look_up
        )
    )
    assert await sim_motor_step.z.user_readback.get_value() == expected_centre


@pytest.mark.parametrize(
    "test_input, expected_centre",
    [(50, 50), (-5, -5), (0, 0)],
)
async def test_motor_with_look_up_move_using_motor_position_success(
    RE: RunEngine, sim_motor_step: XYZStage, test_input, expected_centre
):
    RE(
        move_motor_with_look_up(
            sim_motor_step.z,
            size=test_input,
            motor_table=fake_motor_look_up,
            use_motor_position=True,
        )
    )
    assert await sim_motor_step.z.user_readback.get_value() == expected_centre


@pytest.fixture
async def fake_slit(fake_i10):
    fake_slit = fake_i10["slits"].s5
    set_mock_value(fake_slit.x_gap.velocity, 2.78)
    set_mock_value(fake_slit.y_gap.velocity, 1)

    return fake_slit


async def test_set_slit_size_(RE: RunEngine, fake_slit: Slits):
    set_value = 25
    callback_on_mock_put(
        fake_slit.x_gap.user_setpoint,
        lambda *_, **__: set_mock_value(fake_slit.x_gap.user_readback, set_value),
    )

    callback_on_mock_put(
        fake_slit.y_gap.user_setpoint,
        lambda *_, **__: set_mock_value(fake_slit.y_gap.user_readback, set_value),
    )
    RE(set_slit_size(xy_slit=fake_slit, x_size=set_value))

    assert (
        await fake_slit.x_gap.user_readback.get_value()
        == await fake_slit.y_gap.user_readback.get_value()
        == set_value
    )


@pytest.fixture
async def mock_motor():
    async with init_devices(mock=True):
        mock_motor = Motor("BLxx-MO-xx-01:", "mock_motor")
    yield mock_motor


def test_get_velocity_and_step_size_speed_too_low_failed(
    mock_motor: Motor, RE: RunEngine
):
    with pytest.raises(ValueError):
        RE(
            get_velocity_and_step_size(
                scan_motor=mock_motor, ideal_velocity=-1, ideal_step_size=0.1
            )
        )
