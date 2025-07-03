import asyncio
import math as mt

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from aioca import caput
from bluesky.utils import MsgGenerator
from dodal.common.coordination import inject
from dodal.plan_stubs.data_session import attach_data_session_metadata_decorator
from ophyd_async.core import (
    DetectorTrigger,
    StandardFlyer,
    TriggerInfo,
    wait_for_value,
)
from ophyd_async.epics.pmac import (
    Pmac,
    PmacMotor,
    PmacTrajectoryTriggerLogic,
    PmacTrajInfo,
)
from ophyd_async.fastcs.panda import (
    HDFPanda,
    PandaPcompDirection,
    PcompInfo,
    StaticPcompTriggerLogic,
)
from ophyd_async.fastcs.panda._block import PcompBlock
from ophyd_async.plan_stubs import ensure_connected
from scanspec.specs import Line, fly

X_MOTOR_RESOLUTION = -2 / 100000


class _StaticPcompTriggerLogic(StaticPcompTriggerLogic):
    """For controlling the PandA `PcompBlock` when flyscanning."""

    def __init__(self, pcomp: PcompBlock) -> None:
        self.pcomp = pcomp

    async def kickoff(self) -> None:
        await wait_for_value(self.pcomp.active, True, timeout=1)

    async def prepare(self, value: PcompInfo) -> None:
        await caput("BL99P-MO-PANDA-01:SRGATE1:FORCE_RST", "1", wait=True)
        await asyncio.gather(
            self.pcomp.start.set(value.start_postion),
            self.pcomp.width.set(value.pulse_width),
            self.pcomp.step.set(value.rising_edge_step),
            self.pcomp.pulses.set(value.number_of_pulses),
            self.pcomp.dir.set(value.direction),
        )

    async def stop(self):
        pass


def get_pcomp_info(width, start_pos, direction_of_sweep: PandaPcompDirection, num):
    start_pos_pcomp = mt.floor(start_pos / X_MOTOR_RESOLUTION)
    rising_edge_step = mt.ceil(abs(width / X_MOTOR_RESOLUTION))

    panda_pcomp_info = PcompInfo(
        start_postion=start_pos_pcomp,
        pulse_width=1,
        rising_edge_step=rising_edge_step,
        number_of_pulses=num,
        direction=direction_of_sweep,
    )

    return panda_pcomp_info


def calculate_stuff(start, stop, num):
    width = (stop - start) / (num - 1)
    direction_of_sweep = (
        PandaPcompDirection.POSITIVE
        if width / X_MOTOR_RESOLUTION > 0
        else PandaPcompDirection.NEGATIVE
    )

    return width, start, stop, direction_of_sweep


def trajectory_fly_scan(
    fast_start: float,
    fast_stop: float,
    fast_num: int,
    slow_start: float,
    slow_stop: float,
    slow_num: int,
    duration: float,
    panda: HDFPanda = inject("panda"),  # noqa: B008
) -> MsgGenerator:
    panda_pcomp1 = StandardFlyer(_StaticPcompTriggerLogic(panda.pcomp[1]))
    panda_pcomp2 = StandardFlyer(_StaticPcompTriggerLogic(panda.pcomp[2]))

    pmac = Pmac(prefix="BL99P-MO-STEP-01", name="pmac")
    motor_x = PmacMotor(prefix="BL99P-MO-STAGE-02:X", name="X")
    motor_y = PmacMotor(prefix="BL99P-MO-STAGE-02:Y", name="Y")
    yield from ensure_connected(pmac, motor_x, motor_y)

    # spec = fly(
    #     Repeat(number_of_sweeps, gap=True) * ~Line(motor_x, start, stop, num),
    #     duration,
    # )
    spec = fly(
        Line(motor_y, slow_start, slow_stop, slow_num)
        * ~Line(motor_x, fast_start, fast_stop, fast_num),
        duration,
    )

    info = PmacTrajInfo(spec=spec)

    traj = PmacTrajectoryTriggerLogic(pmac)
    traj_flyer = StandardFlyer(traj)

    @attach_data_session_metadata_decorator()
    @bpp.run_decorator()
    @bpp.stage_decorator([panda, panda_pcomp1, panda_pcomp2])
    def inner_plan():
        width, _, _, direction_of_sweep = calculate_stuff(
            fast_start, fast_stop, fast_num
        )

        dir1 = direction_of_sweep
        dir2 = (
            PandaPcompDirection.POSITIVE
            if direction_of_sweep == PandaPcompDirection.NEGATIVE
            else PandaPcompDirection.NEGATIVE
        )

        pcomp_info1 = get_pcomp_info(width, fast_start, dir1, fast_num)
        pcomp_info2 = get_pcomp_info(width, fast_stop, dir2, fast_num)

        panda_hdf_info = TriggerInfo(
            number_of_events=fast_num * slow_num,
            trigger=DetectorTrigger.CONSTANT_GATE,
            livetime=duration,
            deadtime=1e-5,
        )

        yield from bps.prepare(traj_flyer, info, wait=True)
        # prepare both pcomps
        yield from bps.prepare(panda_pcomp1, pcomp_info1, wait=True)
        yield from bps.prepare(panda_pcomp2, pcomp_info2, wait=True)
        # prepare panda and hdf writer once, at start of scan
        yield from bps.prepare(panda, panda_hdf_info, wait=True)

        yield from bps.kickoff(panda, wait=True)
        yield from bps.kickoff(traj_flyer, wait=True)

        yield from bps.complete_all(traj_flyer, panda, wait=True)

    yield from inner_plan()
