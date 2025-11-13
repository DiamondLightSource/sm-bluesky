from unittest.mock import ANY, Mock, patch

from bluesky.run_engine import RunEngine
from bluesky.simulators import RunEngineSimulator
from dodal.devices.i10.rasor.rasor_motors import DetSlits, PaStage
from dodal.devices.i10.slits import I10Slits
from dodal.devices.motors import XYStage
from ophyd_async.testing import (
    callback_on_mock_put,
    get_mock_put,
    set_mock_value,
)

from sm_bluesky.beamlines.i10.configuration.default_setting import (
    DSD_DSU_OPENING_POS,
    PIN_HOLE_OPEING_POS,
    S5S6_OPENING_SIZE,
)
from sm_bluesky.beamlines.i10.plans import (
    clear_beam_path,
    direct_beam_polan,
    open_dsd_dsu,
    open_s5s6,
    remove_pin_hole,
)
from tests.helpers import check_msg_set, check_msg_wait


async def test_open_s5s6_with_default(
    sim_run_engine: RunEngineSimulator, slits: I10Slits
) -> None:
    msgs = sim_run_engine.simulate_plan(open_s5s6(slits=slits))
    msgs = check_msg_set(msgs=msgs, obj=slits.s5.x_gap, value=S5S6_OPENING_SIZE)
    msgs = check_msg_set(msgs=msgs, obj=slits.s5.y_gap, value=S5S6_OPENING_SIZE)
    msgs = check_msg_set(msgs=msgs, obj=slits.s6.x_gap, value=S5S6_OPENING_SIZE)
    msgs = check_msg_set(msgs=msgs, obj=slits.s6.y_gap, value=S5S6_OPENING_SIZE)
    group = f"{slits.name}__wait"
    msgs = check_msg_wait(msgs=msgs, wait_group=group)
    assert len(msgs) == 1


async def test_open_s5s6_with_other_size(
    sim_run_engine: RunEngineSimulator, slits: I10Slits
) -> None:
    other_value = 0.5
    msgs = sim_run_engine.simulate_plan(open_s5s6(other_value, slits=slits))
    msgs = check_msg_set(msgs=msgs, obj=slits.s5.x_gap, value=other_value)
    msgs = check_msg_set(msgs=msgs, obj=slits.s5.y_gap, value=other_value)
    msgs = check_msg_set(msgs=msgs, obj=slits.s6.x_gap, value=other_value)
    msgs = check_msg_set(msgs=msgs, obj=slits.s6.y_gap, value=other_value)
    group = f"{slits.name}__wait"
    msgs = check_msg_wait(msgs=msgs, wait_group=group)
    assert len(msgs) == 1


async def test_open_s5s6_with_no_wait(
    sim_run_engine: RunEngineSimulator, slits: I10Slits
) -> None:
    other_value = 0.5
    msgs = sim_run_engine.simulate_plan(open_s5s6(other_value, wait=False, slits=slits))
    msgs = check_msg_set(msgs=msgs, obj=slits.s5.x_gap, value=other_value)
    msgs = check_msg_set(msgs=msgs, obj=slits.s5.y_gap, value=other_value)
    msgs = check_msg_set(msgs=msgs, obj=slits.s6.x_gap, value=other_value)
    msgs = check_msg_set(msgs=msgs, obj=slits.s6.y_gap, value=other_value)
    assert len(msgs) == 1


async def test_open_dsd_dsu_with_default(
    sim_run_engine: RunEngineSimulator, det_slits: DetSlits
) -> None:
    msgs = sim_run_engine.simulate_plan(open_dsd_dsu(det_slits=det_slits))
    msgs = check_msg_set(msgs=msgs, obj=det_slits.upstream, value=DSD_DSU_OPENING_POS)
    msgs = check_msg_set(msgs=msgs, obj=det_slits.downstream, value=DSD_DSU_OPENING_POS)
    group = f"{det_slits.name}_wait"
    msgs = check_msg_wait(msgs=msgs, wait_group=group)
    assert len(msgs) == 1


async def test_open_dsd_dsu_with_other_size(
    sim_run_engine: RunEngineSimulator, det_slits: DetSlits
) -> None:
    other_value = 0.5
    msgs = sim_run_engine.simulate_plan(open_dsd_dsu(other_value, det_slits=det_slits))
    msgs = check_msg_set(msgs=msgs, obj=det_slits.upstream, value=other_value)
    msgs = check_msg_set(msgs=msgs, obj=det_slits.downstream, value=other_value)
    group = f"{det_slits.name}_wait"
    msgs = check_msg_wait(msgs=msgs, wait_group=group)
    assert len(msgs) == 1


async def test_open_dsd_dsu_with_no_wait(
    sim_run_engine: RunEngineSimulator, det_slits: DetSlits
) -> None:
    other_value = 0.5
    msgs = sim_run_engine.simulate_plan(
        open_dsd_dsu(other_value, wait=False, det_slits=det_slits)
    )
    msgs = check_msg_set(msgs=msgs, obj=det_slits.upstream, value=other_value)
    msgs = check_msg_set(msgs=msgs, obj=det_slits.downstream, value=other_value)
    assert len(msgs) == 1


async def test_remove_pin_hole_with_default(
    run_engine: RunEngine, pin_hole: XYStage
) -> None:
    callback_on_mock_put(
        pin_hole.x.user_setpoint,
        lambda *_, **__: set_mock_value(pin_hole.x.user_readback, PIN_HOLE_OPEING_POS),
    )

    run_engine(remove_pin_hole(pin_hole=pin_hole))
    get_mock_put(pin_hole.x.user_setpoint).assert_called_once_with(
        PIN_HOLE_OPEING_POS, wait=ANY
    )
    assert await pin_hole.x.user_readback.get_value() == PIN_HOLE_OPEING_POS


async def test_remove_pin_hole_with_other_value(
    sim_run_engine: RunEngineSimulator, pin_hole: XYStage
) -> None:
    other_value = 0.5
    msgs = sim_run_engine.simulate_plan(
        remove_pin_hole(other_value, wait=True, pin_hole=pin_hole)
    )
    msgs = check_msg_set(msgs=msgs, obj=pin_hole.x, value=other_value)
    group = f"{pin_hole.name}_wait"
    msgs = check_msg_wait(msgs=msgs, wait_group=group)
    assert len(msgs) == 1


async def test_remove_pin_hole_with_no_wait(
    sim_run_engine: RunEngineSimulator, pin_hole: XYStage
) -> None:
    other_value = 0.5
    msgs = sim_run_engine.simulate_plan(
        remove_pin_hole(other_value, wait=False, pin_hole=pin_hole)
    )
    msgs = check_msg_set(msgs=msgs, obj=pin_hole.x, value=other_value)
    assert len(msgs) == 1


async def test_direct_beam_polan(
    sim_run_engine: RunEngineSimulator, pa_stage: PaStage
) -> None:
    other_value = 0.0
    msgs = sim_run_engine.simulate_plan(direct_beam_polan(pa_stage=pa_stage))
    msgs = check_msg_set(msgs=msgs, obj=pa_stage.eta, value=other_value)
    msgs = check_msg_set(msgs=msgs, obj=pa_stage.py, value=other_value)
    msgs = check_msg_set(msgs=msgs, obj=pa_stage.ttp, value=other_value)
    msgs = check_msg_set(msgs=msgs, obj=pa_stage.thp, value=other_value)
    group = f"{pa_stage.name}_wait"
    msgs = check_msg_wait(msgs=msgs, wait_group=group)
    assert len(msgs) == 1


@patch("sm_bluesky.beamlines.i10.plans.open_beam_path.direct_beam_polan")
@patch("sm_bluesky.beamlines.i10.plans.open_beam_path.open_dsd_dsu")
@patch("sm_bluesky.beamlines.i10.plans.open_beam_path.open_s5s6")
@patch("sm_bluesky.beamlines.i10.plans.open_beam_path.remove_pin_hole")
async def test_clear_beam_path(
    direct_beam_polan: Mock,
    open_dsd_dsu: Mock,
    open_s5s6: Mock,
    remove_pin_hole: Mock,
    run_engine: RunEngine,
    slits: I10Slits,
    det_slits: DetSlits,
    pin_hole: XYStage,
    pa_stage: PaStage,
) -> None:
    run_engine(
        clear_beam_path(
            slits=slits, det_slits=det_slits, pin_hole=pin_hole, pa_stage=pa_stage
        )
    )
    direct_beam_polan.assert_called_once()
    open_dsd_dsu.assert_called_once()
    open_s5s6.assert_called_once()
    remove_pin_hole.assert_called_once()
