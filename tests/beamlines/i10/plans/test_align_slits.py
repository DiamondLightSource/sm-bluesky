from collections import defaultdict
from typing import Any
from unittest.mock import ANY, MagicMock, patch

import pytest
from bluesky.simulators import RunEngineSimulator
from dodal.devices.current_amplifiers import CurrentAmpDet
from dodal.devices.i10.rasor.rasor_motors import (
    DetSlits,
    Diffractometer,
)
from dodal.devices.i10.slits import I10Slits
from dodal.devices.motors import XYZStage
from ophyd_async.core import StandardReadable

from sm_bluesky.beamlines.i10.plans.align_slits import (
    DSD,
    DSU,
    align_pa_slit,
    align_s5s6,
    align_slit,
    move_dsd,
    move_dsu,
)
from tests.helpers import check_msg_set, check_msg_wait, check_mv_wait

docs = defaultdict(list)


def capture_emitted(name: str, doc: Any) -> None:
    docs[name].append(doc)


def test_move_dsu(sim_run_engine: RunEngineSimulator, det_slits: DetSlits) -> None:
    msgs = sim_run_engine.simulate_plan(move_dsu(5000, det_slits=det_slits))
    msgs = check_msg_set(msgs=msgs, obj=det_slits.upstream, value=DSU["5000"])
    msgs = check_msg_wait(msgs=msgs, wait_group=ANY, wait=True)
    assert len(msgs) == 1


def test_move_dsd(sim_run_engine: RunEngineSimulator, det_slits: DetSlits) -> None:
    msgs = sim_run_engine.simulate_plan(move_dsd(50, det_slits=det_slits))
    msgs = check_msg_set(msgs=msgs, obj=det_slits.downstream, value=DSD["50"])
    msgs = check_msg_wait(msgs=msgs, wait_group=ANY, wait=True)
    assert len(msgs) == 1


@patch(
    "sm_bluesky.beamlines.i10.plans.align_slits.align_slit_with_look_up",
)
def test_align_pa_slit(
    fake_step_scan_and_move_fit: MagicMock,
    sim_run_engine: RunEngineSimulator,
    rasor_femto_pa_scaler_det: CurrentAmpDet,
    det_slits: DetSlits,
):
    msgs = sim_run_engine.simulate_plan(
        align_pa_slit(
            dsd_size=50, dsu_size=50, det=rasor_femto_pa_scaler_det, det_slits=det_slits
        )
    )
    msgs = check_msg_set(msgs=msgs, obj=det_slits.downstream, value=DSD["5000"])
    msgs = check_msg_wait(msgs=msgs, wait_group=ANY, wait=True)

    assert len(msgs) == 1
    assert fake_step_scan_and_move_fit.call_count == 2


@patch(
    "sm_bluesky.beamlines.i10.plans.align_slits.align_slit",
)
def test_align_s5s6(
    mock_align_slit: MagicMock,
    sim_run_engine: RunEngineSimulator,
    rasor_femto_pa_scaler_det: StandardReadable,
    slits: I10Slits,
    diffractometer: Diffractometer,
    sample_stage: XYZStage,
):
    msgs = sim_run_engine.simulate_plan(
        align_s5s6(
            det=rasor_femto_pa_scaler_det,
            slits=slits,
            diffractometer=diffractometer,
            sample_stage=sample_stage,
        )
    )
    assert mock_align_slit.call_count == 2
    msgs = check_msg_set(msgs=msgs, obj=diffractometer.tth, value=0)
    msgs = check_msg_set(msgs=msgs, obj=diffractometer.th, value=0)
    msgs = check_msg_set(msgs=msgs, obj=sample_stage.y, value=-3)
    msgs = check_msg_wait(msgs=msgs, wait_group="diff group A")
    assert len(msgs) == 1


@patch(
    "sm_bluesky.beamlines.i10.plans.align_slits.cal_range_num", return_value=[1, 1, 1]
)
@patch(
    "sm_bluesky.beamlines.i10.plans.align_slits.step_scan_and_move_fit",
)
@pytest.mark.parametrize(
    """x_scan_size, x_final_size, x_open_size, y_scan_size, y_final_size,
      y_open_size, x_range, x_cen, y_range, y_cen""",
    [
        (0, 1, 2, 3.4, 5, 6, 7, 8, 9, 10),
    ],
)
def test_align_slit(
    mock_step_scan: MagicMock,
    mock_cal_range: MagicMock,
    sim_run_engine: RunEngineSimulator,
    x_scan_size: float,
    x_final_size: float,
    x_open_size: float,
    y_scan_size: float,
    y_final_size: float,
    y_open_size: float,
    x_range: float,
    x_cen: float,
    y_range: float,
    y_cen: float,
    rasor_femto_pa_scaler_det: StandardReadable,
    slits: I10Slits,
) -> None:
    slit = slits.s5
    msgs = sim_run_engine.simulate_plan(
        align_slit(
            rasor_femto_pa_scaler_det,
            slit,
            x_scan_size,
            x_final_size,
            x_open_size,
            y_scan_size,
            y_final_size,
            y_open_size,
            x_range,
            x_cen,
            y_range,
            y_cen,
        )
    )
    msgs = check_msg_set(msgs=msgs, obj=slit.x_gap, value=x_scan_size)
    msgs = check_msg_set(msgs=msgs, obj=slit.y_gap, value=y_open_size)
    msgs = check_msg_wait(msgs=msgs, wait_group="slits group")
    msgs = check_msg_set(msgs=msgs, obj=slit.y_centre, value=y_cen)
    msgs = check_mv_wait(msgs=msgs, wait_group=ANY)
    msgs = check_msg_set(msgs=msgs, obj=slit.y_gap, value=y_scan_size)

    msgs = check_msg_set(msgs=msgs, obj=slit.x_gap, value=x_open_size)
    msgs = check_msg_wait(msgs=msgs, wait_group="slits group")
    msgs = check_msg_set(msgs=msgs, obj=slit.x_gap, value=x_final_size)
    msgs = check_msg_set(msgs=msgs, obj=slit.y_gap, value=y_final_size)
    msgs = check_msg_wait(msgs=msgs, wait_group="slits group")
    assert len(msgs) == 1
    assert mock_step_scan.call_count == 2
    assert mock_cal_range.call_count == 2
