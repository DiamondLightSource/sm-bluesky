from collections import defaultdict
from typing import Any
from unittest.mock import Mock, call, patch

from bluesky.run_engine import RunEngine
from bluesky.simulators import RunEngineSimulator
from dodal.devices.current_amplifiers import CurrentAmpDet
from dodal.devices.i10.rasor.rasor_motors import Diffractometer
from dodal.devices.motors import XYZStage

from sm_bluesky.beamlines.i10.configuration.default_setting import (
    RASOR_DEFAULT_DET_NAME_EXTENSION,
)
from sm_bluesky.beamlines.i10.plans import (
    centre_alpha,
    centre_det_angles,
    centre_tth,
    move_pin_origin,
)
from sm_bluesky.common.plans import StatPosition
from tests.helpers import check_msg_set, check_msg_wait

docs = defaultdict(list)


def capture_emitted(name: str, doc: Any) -> None:
    docs[name].append(doc)


@patch("sm_bluesky.beamlines.i10.plans.centre_direct_beam.step_scan_and_move_fit")
async def test_centre_tth(
    fake_step_scan_and_move_fit: Mock,
    RE: RunEngine,
    rasor_femto_pa_scaler_det: CurrentAmpDet,
    diffractometer: Diffractometer,
) -> None:
    RE(
        centre_tth(rasor_femto_pa_scaler_det, diffractometer=diffractometer),
        capture_emitted,
    )
    fake_step_scan_and_move_fit.assert_called_once_with(
        det=rasor_femto_pa_scaler_det,
        motor=diffractometer.tth,
        start=-1,
        end=1,
        num=21,
        detname_suffix=RASOR_DEFAULT_DET_NAME_EXTENSION,
        fitted_loc=StatPosition.CEN,
    )


@patch("sm_bluesky.beamlines.i10.plans.centre_direct_beam.step_scan_and_move_fit")
async def test_centre_alpha(
    fake_step_scan_and_move_fit: Mock,
    RE: RunEngine,
    rasor_femto_pa_scaler_det: CurrentAmpDet,
    diffractometer: Diffractometer,
) -> None:
    RE(centre_alpha(rasor_femto_pa_scaler_det, diffractometer=diffractometer))

    fake_step_scan_and_move_fit.assert_called_once_with(
        det=rasor_femto_pa_scaler_det,
        motor=diffractometer.alpha,
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
    rasor_femto_pa_scaler_det: CurrentAmpDet,
    diffractometer: Diffractometer,
) -> None:
    RE(centre_det_angles(rasor_femto_pa_scaler_det, diffractometer=diffractometer))
    assert fake_step_scan_and_move_fit.call_args_list[0] == call(
        det=rasor_femto_pa_scaler_det,
        motor=diffractometer.tth,
        start=-1,
        end=1,
        num=21,
        detname_suffix=RASOR_DEFAULT_DET_NAME_EXTENSION,
        fitted_loc=StatPosition.CEN,
    )
    assert fake_step_scan_and_move_fit.call_args_list[1] == call(
        det=rasor_femto_pa_scaler_det,
        motor=diffractometer.alpha,
        start=-0.8,
        end=0.8,
        num=21,
        detname_suffix=RASOR_DEFAULT_DET_NAME_EXTENSION,
        fitted_loc=StatPosition.CEN,
    )


def test_move_pin_origin_default(
    sim_run_engine: RunEngineSimulator, sample_stage: XYZStage
) -> None:
    msgs = sim_run_engine.simulate_plan(move_pin_origin(sample_stage=sample_stage))
    msgs = check_msg_set(msgs=msgs, obj=sample_stage.x, value=0)
    msgs = check_msg_set(msgs=msgs, obj=sample_stage.y, value=0)
    msgs = check_msg_set(msgs=msgs, obj=sample_stage.z, value=0)
    msgs = check_msg_wait(msgs=msgs, wait_group="move_pin_origin")
    assert len(msgs) == 1


def test_move_pin_origin_default_without_wait(
    sim_run_engine: RunEngineSimulator, sample_stage: XYZStage
) -> None:
    msgs = sim_run_engine.simulate_plan(
        move_pin_origin(wait=False, sample_stage=sample_stage)
    )
    msgs = check_msg_set(msgs=msgs, obj=sample_stage.x, value=0)
    msgs = check_msg_set(msgs=msgs, obj=sample_stage.y, value=0)
    msgs = check_msg_set(msgs=msgs, obj=sample_stage.z, value=0)
    assert len(msgs) == 1
