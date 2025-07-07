from typing import Any

from blueapi.core import MsgGenerator
from bluesky import plan_stubs as bps
from bluesky import preprocessors as bpp
from bluesky.utils import Msg, plan
from dodal.plan_stubs.data_session import attach_data_session_metadata_decorator
from ophyd_async.epics.adandor import Andor2Detector


@plan
@attach_data_session_metadata_decorator()
def tigger_img(
    dets: Andor2Detector, value: int, md: dict[str, Any] | None = None
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
    yield Msg("set", dets.driver.acquire_time, value)

    @bpp.stage_decorator([dets])
    @bpp.run_decorator(md=md)
    def innertigger_img():
        return (yield from bps.trigger_and_read([dets]))

    yield from innertigger_img()
