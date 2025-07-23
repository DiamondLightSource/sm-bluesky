from typing import TypeVar

import bluesky.plan_stubs as bps
from bluesky import preprocessors as bpp
from bluesky.plan_stubs import abs_set, sleep
from bluesky.protocols import Movable
from bluesky.utils import plan

t = TypeVar("t", bound=Movable)


def set_setpoint_to_readback(set_signal, readback_signal):
    a = yield from bps.rd(readback_signal)
    yield from bps.abs_set(set_signal, a, wait=True)


@plan
def set_and_wait_within_tolerance(
    set_signal,
    value,
    readback_signal,
    tolerance,
    plan=None,
    final_plan=set_setpoint_to_readback,
):
    if plan is None:
        plan = sleep(0.1)
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
        final_plan=final_plan(set_signal, readback_signal),
    )
