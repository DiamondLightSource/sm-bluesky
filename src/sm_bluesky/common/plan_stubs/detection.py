from typing import Any

import bluesky.plan_stubs as bps
from blueapi.core import MsgGenerator
from bluesky.plan_stubs import abs_set
from bluesky.protocols import Flyable
from bluesky.utils import plan, short_uid
from ophyd_async.core import FlyMotorInfo
from ophyd_async.epics.adcore import AreaDetector, SingleTriggerDetector

from sm_bluesky.log import LOGGER


@plan
def set_area_detector_acquire_time(
    det: AreaDetector | SingleTriggerDetector, acquire_time: float, wait: bool = True
) -> MsgGenerator:
    """
    Set the acquire time on an area detector.

    Parameters
    ----------
    det : AreaDetector | SingleTriggerDetector
        The detector whose acquire time is to be set.
    acquire_time : float
        The desired acquire time.
    wait : bool, optional
        Whether to wait for the operation to complete, by default True.

    Returns
    -------
    MsgGenerator
        A Bluesky generator for setting the acquire time.
    """
    drv = det.drv if isinstance(det, SingleTriggerDetector) else det.driver
    yield from abs_set(drv.acquire_time, acquire_time, wait=wait)


@plan
def fly_trigger_and_read(
    motor: Flyable,
    fly_info: FlyMotorInfo,
    dets: list[Any],
) -> MsgGenerator:
    grp = short_uid("kickoff")
    yield from bps.kickoff(motor, group=grp, wait=True)
    LOGGER.info(f"flying motor =  {motor.name} at with info = {fly_info}")
    done = yield from bps.complete(motor)
    yield from bps.trigger_and_read(dets + [motor])
    while not done.done:
        yield from bps.trigger_and_read(dets + [motor])
        yield from bps.checkpoint()
