import bluesky.plan_stubs as bps
from bluesky import preprocessors as bpp
from bluesky.plan_stubs import abs_set, sleep
from bluesky.protocols import Movable, Readable
from bluesky.utils import MsgGenerator, plan

MR = type("MR", (Movable, Readable), {"MR": "MR"})


def set_setpoint_to_readback(set_signal, readback_signal) -> MsgGenerator:
    a = yield from bps.rd(readback_signal)
    yield from bps.abs_set(set_signal, a, wait=True)


@plan
def set_and_wait_within_tolerance(
    set_signal: MR,
    value: float,
    tolerance: float,
    readback_signal: Readable | None = None,
    plan: MsgGenerator | None = None,
    final_plan: MsgGenerator | None = None,
):
    if plan is None:
        plan = sleep(1)
    if readback_signal is None:
        readback_signal = set_signal
    if final_plan is None:
        final_plan = set_setpoint_to_readback(set_signal, readback_signal)
    yield from abs_set(set_signal, value, wait=False)

    def inner_plan():
        set = yield from bps.rd(set_signal)
        readback = yield from bps.rd(readback_signal)
        while abs(readback - set) > tolerance:
            yield from plan
            readback = yield from bps.rd(readback_signal)
            yield from bps.checkpoint()

    yield from bpp.finalize_wrapper(
        plan=inner_plan(),
        final_plan=final_plan,
    )
