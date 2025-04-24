from blueapi.core import MsgGenerator
from bluesky.plan_stubs import abs_set
from bluesky.utils import plan
from ophyd_async.epics.adcore import AreaDetector, SingleTriggerDetector


@plan
def set_area_detector_acquire_time(
    det: AreaDetector | SingleTriggerDetector, acquire_time: float, wait: bool = True
) -> MsgGenerator[None]:
    # Set count time on detector

    drv = det.drv if isinstance(det, SingleTriggerDetector) else det.driver
    yield from abs_set(drv.acquire_time, acquire_time, wait=wait)
