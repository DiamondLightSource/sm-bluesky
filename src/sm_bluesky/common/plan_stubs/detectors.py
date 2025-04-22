from blueapi.core import MsgGenerator
from bluesky.plan_stubs import abs_set
from ophyd_async.epics.adcore import AreaDetector, SingleTriggerDetector


def set_area_detector_acquire_time(
    det: AreaDetector | SingleTriggerDetector, acquire_time: float, wait: bool = True
) -> MsgGenerator:
    # Set count time on detector
    if isinstance(det, SingleTriggerDetector):
        yield from abs_set(det.drv.acquire_time, acquire_time, wait=wait)
    else:
        yield from abs_set(det.driver.acquire_time, acquire_time, wait=wait)
