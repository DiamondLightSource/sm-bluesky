from collections.abc import Sequence

import bluesky.plan_stubs as bps
from bluesky.plan_stubs import abs_set
from bluesky.protocols import Flyable, Readable
from bluesky.utils import MsgGenerator, plan, short_uid
from dodal.devices.single_trigger_detector import SingleTriggerDetector
from ophyd_async.epics.adcore import AreaDetector


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
def fly_kickoff_complete(
    flyable: Flyable,
    dets: Sequence[Readable],
    trigger_and_read: bps.TakeReading | None = None,
) -> MsgGenerator:
    if trigger_and_read is None:
        trigger_and_read = bps.trigger_and_read
    grp = short_uid("kickoff")
    yield from bps.kickoff(flyable, group=grp, wait=True)
    status = yield from bps.complete(flyable)
    yield from trigger_and_read(dets)
    while not status.done:
        yield from trigger_and_read(dets)
        yield from bps.checkpoint()
