from math import ceil, floor

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from bluesky.utils import MsgGenerator, plan
from dodal.plan_stubs.data_session import attach_data_session_metadata_decorator
from ophyd_async.core import (
    DetectorTrigger,
    StandardFlyer,
    TriggerInfo,
)
from ophyd_async.epics.motor import Motor
from ophyd_async.epics.pmac import PmacIO
from ophyd_async.epics.pmac._pmac_trajectory import (
    PmacTrajectoryTriggerLogic,  # noqa: PLC2701
)
from ophyd_async.fastcs.panda import (
    HDFPanda,
    PandaPcompDirection,
    PcompInfo,
    StaticPcompTriggerLogic,
)
from scanspec.specs import Fly, Line

X_MOTOR_RESOLUTION = -2 / 100000


def calculate_stuff(start, stop, num):
    width = (stop - start) / (num - 1)
    direction_of_sweep = (
        PandaPcompDirection.POSITIVE
        if width / X_MOTOR_RESOLUTION > 0
        else PandaPcompDirection.NEGATIVE
    )

    return width, start, stop, direction_of_sweep


def get_pcomp_info(width, start_pos, direction_of_sweep: PandaPcompDirection, num):
    start_pos_pcomp = floor(start_pos / X_MOTOR_RESOLUTION)
    rising_edge_step = ceil(abs(width / X_MOTOR_RESOLUTION))

    panda_pcomp_info = PcompInfo(
        start_postion=start_pos_pcomp,
        pulse_width=1,
        rising_edge_step=rising_edge_step,
        number_of_pulses=num,
        direction=direction_of_sweep,
    )

    return panda_pcomp_info


@plan
def trajectory_fly_scan(
    motor_fast: Motor,
    motor_slow: Motor,
    pmac: PmacIO,
    fast_start: float,
    fast_stop: float,
    fast_num: int,
    slow_start: float,
    slow_stop: float,
    slow_num: int,
    duration: float,
    panda: HDFPanda,  # noqa: B008
) -> MsgGenerator:
    panda_pcomp1 = StandardFlyer(StaticPcompTriggerLogic(panda.pcomp[1]))
    panda_pcomp2 = StandardFlyer(StaticPcompTriggerLogic(panda.pcomp[2]))
    spec = Fly(
        duration
        @ (
            Line(motor_slow, slow_start, slow_stop, slow_num)  # type: ignore
            * ~Line(motor_slow, fast_start, fast_stop, fast_num)  # type: ignore
        )  # type: ignore
    )

    pmac_trajectory = PmacTrajectoryTriggerLogic(pmac)
    pmac_trajectory_flyer = StandardFlyer(pmac_trajectory)

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
        yield from bps.prepare(pmac_trajectory_flyer, spec, wait=True)
        # prepare both pcomps
        yield from bps.prepare(panda_pcomp1, pcomp_info1, wait=True)
        yield from bps.prepare(panda_pcomp2, pcomp_info2, wait=True)
        # prepare panda and hdf writer once, at start of scan
        yield from bps.prepare(panda, panda_hdf_info, wait=True)

        yield from bps.kickoff(panda, wait=True)
        yield from bps.kickoff(pmac_trajectory_flyer, wait=True)

        yield from bps.complete_all(pmac_trajectory_flyer, panda, wait=True)

    yield from inner_plan()
