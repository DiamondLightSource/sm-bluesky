from collections import defaultdict
from unittest.mock import Mock, call, patch

import numpy as np
import pytest
from bluesky.run_engine import RunEngine
from bluesky.simulators import RunEngineSimulator
from dodal.beamlines.i10 import diffractometer, sample_stage
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
async def test_centre_alpha(fake_step_scan_and_move_fit: Mock, RE: RunEngine, fake_i10):
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
        num=test_input[5] + 1,
        type=math_functions.step_function,
        centre=expected_centre[1],
    )
    y_data = np.append(y_data, [0])
    y_data = np.array(y_data, dtype=np.float64)
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
        type=math_functions.gaussian,
        centre=expected_centre[0],
        sig=0.1,
    )

    m_y_data = np.append(m_y_data, [0])
    m_y_data = np.array(m_y_data, dtype=np.float64)
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
