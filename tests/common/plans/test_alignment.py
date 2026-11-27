from collections.abc import Mapping
from unittest.mock import Mock

import numpy as np
import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.motors import XYZStage
from ophyd_async.core import callback_on_mock_put, set_mock_value
from ophyd_async.epics.motor import Motor

from sm_bluesky.common.math import cal_range_num
from sm_bluesky.common.plans import (
    StatPosition,
    align_slit_with_look_up,
    fast_scan_and_move_fit,
    step_scan_and_move_fit,
)
from tests.helpers import FakeDetector, gaussian


def move_and_update_detector(motor: Motor, det: FakeDetector, det_values: Mock):
    """Mock put callback that instantly moves the motor readback to the
    setpoint and updates the detector with the next value."""

    def _callback(value: float, *_, **__) -> None:
        set_mock_value(motor.user_readback, value)
        set_mock_value(det.value, det_values.get())

    return _callback


@pytest.mark.parametrize(
    "test_input, expected_centre",
    [
        (
            (5, -5, 21, 0.1),
            -1,
        ),
        (
            (50, -55, 21, 1),
            21.1,
        ),
        (
            (-1, -2.51241, 21, 0.05),
            -1.2,
        ),
    ],
)
async def test_scan_and_move_cen_success_with_gaussian(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    sim_stage: XYZStage,
    fake_detector: FakeDetector,
    test_input: tuple[float, float, int, float],
    expected_centre: float,
) -> None:
    start = test_input[0]
    end = test_input[1]
    num = test_input[2]
    peak_width = test_input[3]
    cen = expected_centre
    # Generate gaussian
    x_data = np.linspace(start, end, num, endpoint=True)
    y_data = gaussian(x_data, cen, peak_width)

    rbv_mocks = Mock()
    y_data = np.append(y_data, [0] * 2)
    y_data = np.array(y_data, dtype=np.float64)
    rbv_mocks.get.side_effect = y_data
    callback_on_mock_put(
        sim_stage.x.user_setpoint,
        move_and_update_detector(sim_stage.x, fake_detector, rbv_mocks),
    )
    run_engine(
        step_scan_and_move_fit(
            fake_detector,
            sim_stage.x,
            StatPosition.COM,
            "value",
            start,
            end,
            num,
        ),
    )
    y_data1 = np.array([])
    x_data1 = np.array([])
    for i in run_engine_documents["event"]:
        y_data1 = np.append(y_data1, i["data"]["fake_detector-value"])
        x_data1 = np.append(x_data1, i["data"]["sim_stage-x"])
    assert await sim_stage.x.user_setpoint.get_value() == pytest.approx(
        expected_centre, 0.01
    )


def step_function(x_data, step_centre: float) -> list[float]:
    return [0 if x < step_centre else 1 for x in x_data]


@pytest.mark.parametrize(
    "test_input, expected_centre",
    [
        (
            (1, -2, 44),
            -1,
        ),
        (
            (0.1, 0.5, 20),
            0.2,
        ),
    ],
)
async def test_scan_and_move_cen_success_with_step(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    sim_stage: XYZStage,
    fake_detector: FakeDetector,
    test_input: tuple[float, float, int],
    expected_centre: float,
) -> None:
    start = test_input[0]
    end = test_input[1]
    num = int(test_input[2])
    cen = expected_centre
    # Generate a step
    x_data = np.linspace(start, end, num, endpoint=True)
    y_data = step_function(x_data, cen)

    rbv_mocks = Mock()
    y_data = np.append(y_data, [0] * 2)
    y_data = np.array(y_data, dtype=np.float64)
    rbv_mocks.get.side_effect = y_data
    callback_on_mock_put(
        sim_stage.x.user_setpoint,
        move_and_update_detector(sim_stage.x, fake_detector, rbv_mocks),
    )
    run_engine(
        step_scan_and_move_fit(
            det=fake_detector,
            motor=sim_stage.x,
            start=start,
            detname_suffix="value",
            end=end,
            num=num,
            fitted_loc=StatPosition.D_CEN,
        ),
    )
    y_data1 = np.array([])
    x_data1 = np.array([])
    for i in run_engine_documents["event"]:
        y_data1 = np.append(y_data1, i["data"]["fake_detector-value"])
        x_data1 = np.append(x_data1, i["data"]["sim_stage-x"])
    assert await sim_stage.x.user_setpoint.get_value() == pytest.approx(
        expected_centre, 0.05
    )


async def test_scan_and_move_cen_fail_to_with_wrong_name(
    run_engine: RunEngine,
    sim_motor: XYZStage,
    fake_detector: FakeDetector,
) -> None:
    rbv_mocks = Mock()
    y_data = range(0, 19999, 1)
    rbv_mocks.get.side_effect = y_data
    callback_on_mock_put(
        sim_motor.x.user_setpoint,
        lambda *_, **__: set_mock_value(fake_detector.value, value=rbv_mocks.get()),
    )
    sim_motor.x._name = " "
    with pytest.raises(ValueError) as e:
        run_engine(
            fast_scan_and_move_fit(
                det=fake_detector,
                motor=sim_motor.x,
                detname_suffix="dsdfs",
                start=-5,
                end=5,
                fitted_loc=StatPosition.CEN,
                motor_speed=100,
            ),
        )

    assert str(e.value) == "Fitting failed, check devices name are correct."


@pytest.mark.parametrize(
    "test_input, expected_centre",
    [
        (
            (5, -4, 31, 0.1),
            -5.1,
        ),
    ],
)
async def test_scan_and_move_cen_failed_with_no_peak_in_range(
    run_engine: RunEngine,
    sim_stage: XYZStage,
    fake_detector: FakeDetector,
    test_input: tuple[float, float, int, float],
    expected_centre: float,
) -> None:
    start = test_input[0]
    end = test_input[1]
    num = test_input[2]
    peak_width = test_input[3]
    cen = expected_centre
    # Generate gaussian
    x_data = np.linspace(start, end, num, endpoint=True)
    y_data = gaussian(x_data, cen, peak_width)

    rbv_mocks = Mock()
    y_data = np.append(y_data, [0] * 2)
    y_data = np.array(y_data, dtype=np.float64)
    rbv_mocks.get.side_effect = y_data
    callback_on_mock_put(
        sim_stage.x.user_setpoint,
        move_and_update_detector(sim_stage.x, fake_detector, rbv_mocks),
    )
    with pytest.raises(ValueError) as e:
        run_engine(
            step_scan_and_move_fit(
                det=fake_detector,
                motor=sim_stage.x,
                detname_suffix="value",
                start=start,
                end=end,
                fitted_loc=StatPosition.CEN,
                num=num,
            ),
        )
    assert str(e.value) == "Fitting failed, no peak within scan range."


FAKEDSU = {"5000": 16.7, "1000": 21.7, "500": 25.674, "100": 31.7, "50": 36.7}


@pytest.mark.parametrize(
    "size, expected_centre, offset",
    [
        (5000, 16.7, 0.1),
        (1000, 21.7, 0.2),
        (500, 25.6, 0.2),
    ],
)
async def test_align_slit_with_look_up(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    sim_stage: XYZStage,
    fake_detector: FakeDetector,
    size: float,
    expected_centre: float,
    offset: float,
) -> None:
    start, end, num = cal_range_num(
        cen=FAKEDSU[str(size)], range=size / 1000 * 3, size=size / 5000.0
    )
    peak_width = FAKEDSU[str(size)] * 0.5
    cen = FAKEDSU[str(size)] + offset
    # Generate gaussian
    x_data = np.linspace(start, end, num, endpoint=True)
    y_data = gaussian(x_data, cen, peak_width)

    rbv_mocks = Mock()
    y_data = np.append(y_data, [0] * 2)
    y_data = np.array(y_data, dtype=np.float64)
    rbv_mocks.get.side_effect = y_data
    callback_on_mock_put(
        sim_stage.y.user_setpoint,
        move_and_update_detector(sim_stage.y, fake_detector, rbv_mocks),
    )
    run_engine(
        align_slit_with_look_up(
            motor=sim_stage.y,  # type: ignore
            size=size,
            slit_table=FAKEDSU,
            det=fake_detector,
            centre_type=StatPosition.COM,
        ),
    )
    y_data1 = np.array([])
    x_data1 = np.array([])
    for i in run_engine_documents["event"]:
        y_data1 = np.append(y_data1, i["data"]["fake_detector-value"])
        x_data1 = np.append(x_data1, i["data"]["sim_stage-y"])
    assert FAKEDSU[str(size)] == pytest.approx(expected_centre + offset, 0.01)


async def test_align_slit_with_look_up_fail_wrong_key(
    run_engine: RunEngine,
    sim_stage: XYZStage,
    fake_detector: FakeDetector,
) -> None:
    size = 555
    with pytest.raises(ValueError) as e:
        run_engine(
            align_slit_with_look_up(
                motor=sim_stage.y,  # type: ignore
                size=size,
                slit_table=FAKEDSU,
                det=fake_detector,
                centre_type=StatPosition.CEN,
            ),
        )
    assert str(e.value) == f"Size of {size} is not in {FAKEDSU.keys}"
