from typing import Any

from bluesky import plan_stubs as bps
from bluesky import preprocessors as bpp
from bluesky.utils import Msg, MsgGenerator, plan
from ophyd_async.epics.adandor import AndorDetector


@plan
def trigger_img(
    dets: AndorDetector, acquire_time: int, md: dict[str, Any] | None = None
) -> MsgGenerator:
    """
    Set the acquire time and trigger the detector to read data.

    Parameters
    ----------
    dets : Andor2Detector
        The detector to trigger.
    value : int
        The acquire time to set on the detector.

    Returns
    -------
    MsgGenerator
        A Bluesky generator for triggering the detector.
    """
    if md is None:
        md = {}
    yield Msg("set", dets.driver.acquire_time, acquire_time)

    @bpp.stage_decorator([dets])
    @bpp.run_decorator(md=md)
    def inner_trigger_img():
        return (yield from bps.trigger_and_read([dets]))

    yield from inner_trigger_img()
