from typing import Any

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from blueapi.core import MsgGenerator
from bluesky.preprocessors import (
    finalize_wrapper,
)
from bluesky.protocols import Readable
from bluesky.utils import plan
from dodal.devices.apple2_undulator import EnergySetter
from dodal.plan_stubs.data_session import attach_data_session_metadata_decorator
from ophyd_async.core import FlyMotorInfo

from sm_bluesky.common.plan_stubs import (
    cache_speed,
    fly_trigger_and_read,
    restore_speed,
)


@plan
@attach_data_session_metadata_decorator()
def soft_fly_energy_scan(
    energy_device: EnergySetter,
    energy_start: float,
    energy_end: float,
    energy_step: float,
    count_time: float,
    dets: list[Readable],
    md: dict[str, Any] | None = None,
):
    old_speeds = yield from cache_speed(
        [energy_device.pgm_ref().energy, energy_device.id.gap]
    )

    fly_info = FlyMotorInfo(
        start_position=energy_start,
        end_position=energy_end,
        time_for_move=abs(energy_end - energy_start) / energy_step * count_time,
    )

    @bpp.stage_decorator(dets)
    @bpp.run_decorator(md=md)
    def inn_fly_energy_scan(
        energy_device: EnergySetter,
        fly_info: FlyMotorInfo,
        dets: list[Readable],
    ) -> MsgGenerator:
        yield from bps.prepare(energy_device, fly_info, wait=True)
        yield from fly_trigger_and_read(energy_device, fly_info, dets)

    yield from finalize_wrapper(
        plan=inn_fly_energy_scan(energy_device, fly_info, dets),
        final_plan=restore_speed(old_speeds),
    )
