from blueapi.core import MsgGenerator
from bluesky.plan_stubs import abs_set
from bluesky.utils import plan
from ophyd_async.epics.adcore import AreaDetector, SingleTriggerDetector


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
