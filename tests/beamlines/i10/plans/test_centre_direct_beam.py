from collections import defaultdict
from unittest.mock import AsyncMock, Mock, call, patch

import numpy as np
import pytest
from bluesky.run_engine import RunEngine
from bluesky.simulators import RunEngineSimulator
from dodal.beamlines.i10 import Diffractometer, diffractometer, sample_stage
from dodal.devices.i10.mirrors import PiezoMirror
from dodal.devices.motors import XYZStage
from ophyd_async.testing import callback_on_mock_put, set_mock_value

from sm_bluesky.beamlines.i10.configuration.default_setting import (
    RASOR_DEFAULT_DET,
    RASOR_DEFAULT_DET_NAME_EXTENSION,
)
from sm_bluesky.beamlines.i10.plans import (
    beam_on_pin,
    centre_alpha,
    centre_det_angles,
    centre_tth,
    move_pin_origin,
)
from sm_bluesky.beamlines.i10.plans.centre_direct_beam import (
    beam_on_centre_diffractometer,
)
from sm_bluesky.common.plans import (
    StatPosition,
)

from ....helpers import (
    check_msg_set,
    check_msg_wait,
    generate_test_data,
    math_functions,
)
from ....sim_devices import sim_detector

docs = defaultdict(list)


def capture_emitted(name, doc):
    docs[name].append(doc)


@patch("sm_bluesky.beamlines.i10.plans.centre_direct_beam.step_scan_and_move_fit")
async def test_centre_tth(
    fake_step_scan_and_move_fit: Mock,
    RE: RunEngine,
    fake_i10,
):
    RE(centre_tth(), docs)
    fake_step_scan_and_move_fit.assert_called_once_with(
        det=RASOR_DEFAULT_DET,
        motor=diffractometer().tth,
        start=-1,
        end=1,
        num=21,
        detname_suffix=RASOR_DEFAULT_DET_NAME_EXTENSION,
        fitted_loc=StatPosition.CEN,
    )


@patch("sm_bluesky.beamlines.i10.plans.centre_direct_beam.step_scan_and_move_fit")
async def test_centre_alpha(fake_step_scan_and_move_fit: Mock, RE: RunEngine):
    RE(centre_alpha())

    fake_step_scan_and_move_fit.assert_called_once_with(
        det=RASOR_DEFAULT_DET,
        motor=diffractometer().alpha,
        start=-0.8,
        end=0.8,
        num=21,
        detname_suffix=RASOR_DEFAULT_DET_NAME_EXTENSION,
        fitted_loc=StatPosition.CEN,
    )


@patch("sm_bluesky.beamlines.i10.plans.centre_direct_beam.step_scan_and_move_fit")
async def test_centre_det_angles(
    fake_step_scan_and_move_fit: Mock,
    RE: RunEngine,
):
    RE(centre_det_angles())
    assert fake_step_scan_and_move_fit.call_args_list[0] == call(
        det=RASOR_DEFAULT_DET,
        motor=diffractometer().tth,
        start=-1,
        end=1,
        num=21,
        detname_suffix=RASOR_DEFAULT_DET_NAME_EXTENSION,
        fitted_loc=StatPosition.CEN,
    )
    assert fake_step_scan_and_move_fit.call_args_list[1] == call(
        det=RASOR_DEFAULT_DET,
        motor=diffractometer().alpha,
        start=-0.8,
        end=0.8,
        num=21,
        detname_suffix=RASOR_DEFAULT_DET_NAME_EXTENSION,
        fitted_loc=StatPosition.CEN,
    )


def test_move_pin_origin_default():
    sim = RunEngineSimulator()
    msgs = sim.simulate_plan(move_pin_origin())
    msgs = check_msg_set(msgs=msgs, obj=sample_stage().x, value=0)
    msgs = check_msg_set(msgs=msgs, obj=sample_stage().y, value=0)
    msgs = check_msg_set(msgs=msgs, obj=sample_stage().z, value=0)
    msgs = check_msg_wait(msgs=msgs, wait_group="move_pin_origin")
    assert len(msgs) == 1


def test_move_pin_origin_default_without_wait():
    sim = RunEngineSimulator()
    msgs = sim.simulate_plan(move_pin_origin(wait=False))
    msgs = check_msg_set(msgs=msgs, obj=sample_stage().x, value=0)
    msgs = check_msg_set(msgs=msgs, obj=sample_stage().y, value=0)
    msgs = check_msg_set(msgs=msgs, obj=sample_stage().z, value=0)
    assert len(msgs) == 1


@pytest.mark.parametrize(
    "test_input, expected_centre",
    [
        (
            [5.22, 10.2, 51, 1.25, -3.25, 51],
            [6, -2.1],
        ),
        (
            [-3.22, 3.2, 51, -1.25, -3.25, 51],
            [1.7, -2.1],
        ),
    ],
)
@patch("sm_bluesky.beamlines.i10.plans.centre_direct_beam.sample_stage")
@patch("sm_bluesky.beamlines.i10.plans.centre_direct_beam.focusing_mirror")
async def test_beam_on_pin(
    focusing_mirror: Mock,
    sample_stage: Mock,
    RE: RunEngine,
    sim_motor_step: XYZStage,
    fake_detector: sim_detector,
    fake_mirror: PiezoMirror,
    test_input,
    expected_centre,
):
    sample_stage.return_value = sim_motor_step
    y_data = generate_test_data(
        start=test_input[3],
        end=test_input[4],
        num=test_input[5] + 2,
        func=math_functions.step_function,
        centre=expected_centre[1],
    )

    rbv_mocks = Mock()
    rbv_mocks.get.side_effect = y_data
    callback_on_mock_put(
        sim_motor_step.y.user_setpoint,
        lambda *_, **__: set_mock_value(fake_detector.value, value=rbv_mocks.get()),
    )

    focusing_mirror.return_value = fake_mirror

    m_y_data = -1 * generate_test_data(
        start=test_input[0],
        end=test_input[1],
        num=test_input[2] + 1,
        func=math_functions.gaussian,
        centre=expected_centre[0],
        sig=0.1,
    )
    m_rbv_mocks = Mock()
    m_rbv_mocks.get.side_effect = m_y_data

    callback_on_mock_put(
        fake_mirror.fine_pitch,
        lambda *_, **__: set_mock_value(fake_detector.value, value=m_rbv_mocks.get()),
    )

    RE(beam_on_pin(fake_detector, "value", *test_input))
    assert await sim_motor_step.y.user_setpoint.get_value() == pytest.approx(
        expected_centre[1], abs=0.1
    )
    assert await fake_mirror.fine_pitch.get_value() == pytest.approx(
        expected_centre[0], abs=0.2
    )


@pytest.mark.parametrize(
    "test_y_positions",
    [
        (
            [
                -2.0,
                1.0,
                0.7,
                0.5,
                0.3,
                0.1,
                -0.5,
            ]
        ),
        (
            [
                -2.0,
                5.0,
                0.7,
                0.5,
                1.5,
            ]
        ),
    ],
)
@patch("sm_bluesky.beamlines.i10.plans.centre_direct_beam.focusing_mirror")
@patch("sm_bluesky.beamlines.i10.plans.centre_direct_beam.sample_stage")
@patch("sm_bluesky.beamlines.i10.plans.centre_direct_beam.diffractometer")
@patch("sm_bluesky.beamlines.i10.plans.centre_direct_beam.beam_on_pin")
@patch("sm_bluesky.beamlines.i10.plans.centre_direct_beam.centre_det_angles")
@patch("sm_bluesky.beamlines.i10.plans.centre_direct_beam.move_pin_origin")
async def test_beam_on_centre_diffractometer_runs(
    move_pin_origin: Mock,
    centre_det_angles: Mock,
    beam_on_pin: Mock,
    diffractometer: Mock,
    sample_stage: Mock,
    focusing_mirror: Mock,
    sim_motor_step: XYZStage,
    fake_mirror: PiezoMirror,
    fake_detector,
    fake_diffractometer: Diffractometer,
    test_y_positions: list[float],
    RE: RunEngine,
):
    sample_stage.return_value = sim_motor_step
    sample_stage().y.user_readback.get_value = AsyncMock()
    print(test_y_positions)
    sample_stage().y.user_readback.get_value.side_effect = test_y_positions
    focusing_mirror.return_value = fake_mirror
    diffractometer.return_value = fake_diffractometer
    RE(beam_on_centre_diffractometer(fake_detector, "value"))

    assert move_pin_origin.call_count == 1
    assert centre_det_angles.call_count == 1
    assert beam_on_pin.call_count == len(test_y_positions)


@patch("sm_bluesky.beamlines.i10.plans.centre_direct_beam.focusing_mirror")
@patch("sm_bluesky.beamlines.i10.plans.centre_direct_beam.sample_stage")
@patch("sm_bluesky.beamlines.i10.plans.centre_direct_beam.diffractometer")
@patch("sm_bluesky.beamlines.i10.plans.centre_direct_beam.beam_on_pin")
@patch("sm_bluesky.beamlines.i10.plans.centre_direct_beam.centre_det_angles")
@patch("sm_bluesky.beamlines.i10.plans.centre_direct_beam.move_pin_origin")
async def test_beam_on_centre_diffractometer_runs_failed(
    move_pin_origin: Mock,
    centre_det_angles: Mock,
    beam_on_pin: Mock,
    diffractometer: Mock,
    sample_stage: Mock,
    focusing_mirror: Mock,
    sim_motor_step: XYZStage,
    fake_mirror: PiezoMirror,
    fake_detector,
    fake_diffractometer: Diffractometer,
    RE: RunEngine,
):
    sample_stage.return_value = sim_motor_step
    sample_stage().y.user_readback.get_value = AsyncMock()
    test_y_positions = np.random.uniform(-2.0, 5.0, size=10)
    sample_stage().y.user_readback.get_value.side_effect = test_y_positions
    focusing_mirror.return_value = fake_mirror
    diffractometer.return_value = fake_diffractometer
    with pytest.raises(
        RuntimeError,
        match="Failed to centre the pin hole on the beam after 5 iterations.",
    ):
        RE(beam_on_centre_diffractometer(fake_detector, "value"))
