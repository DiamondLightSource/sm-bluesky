from blueapi.core import MsgGenerator
from bluesky import plan_stubs as bps
from bluesky import preprocessors as bpp
from bluesky.utils import Msg, short_uid
from ophyd_async.core import DetectorTrigger, TriggerInfo
from ophyd_async.epics.adandor import Andor2Detector


def takeImg(
    det: Andor2Detector,
    exposure: float,
    n_img: int = 1,
    det_trig: DetectorTrigger = DetectorTrigger.INTERNAL,
) -> MsgGenerator:
    """
    Bare minimum to take an image using prepare plan with full detector control
    e.g. Able to change tigger_info unlike tigger
    """
    grp = short_uid("prepare")
    deadtime: float = det._controller.get_deadtime(exposure)  # noqa: SLF001
    tigger_info = TriggerInfo(
        number_of_triggers=n_img,
        trigger=det_trig,
        deadtime=deadtime,
        livetime=exposure,
        frame_timeout=None,
    )

    @bpp.stage_decorator([det])
    @bpp.run_decorator()
    def innerTakeImg():
        yield from bps.prepare(det, tigger_info, group=grp, wait=True)
        yield from bps.trigger_and_read([det])

    yield from innerTakeImg()


def tiggerImg(dets: Andor2Detector, value: int) -> MsgGenerator:
    yield Msg("set", dets.driver.acquire_time, value)

    @bpp.stage_decorator([dets])
    @bpp.run_decorator()
    def innerTiggerImg():
        return (yield from bps.trigger_and_read([dets]))

    yield from innerTiggerImg()
