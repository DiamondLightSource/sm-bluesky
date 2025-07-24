from collections.abc import Callable, Sequence

import bluesky.plan_stubs as bps
from bluesky import preprocessors as bpp
from bluesky.plan_stubs import abs_set, sleep
from bluesky.protocols import Readable
from bluesky.utils import MsgGenerator, plan
from ophyd_async.core import SignalRW


def set_setpoint_to_readback(
    set_signal: SignalRW, readback_signal: Readable
) -> MsgGenerator:
    """
    Set the set_signal to the current value of readback_signal and wait for completion.
    """
    value = yield from bps.rd(readback_signal)
    yield from bps.abs_set(set_signal, value, wait=True)


@plan
def set_and_wait_within_tolerance(
    set_signal: SignalRW,
    value: float,
    tolerance: float,
    readback_signal: Readable | None = None,
    plan: Callable[..., MsgGenerator] | None = None,
    plan_parm: Sequence | None = None,
    final_plan: MsgGenerator | None = None,
) -> MsgGenerator:
    """
    Set a signal to a value and wait until the readback is within a given tolerance.
    Optionally run a plan between checks and a final plan after completion.

    Parameters
    ----------
    set_signal : SignalRW
        The signal to set.
    value : float
        The target value.
    tolerance : float
        Acceptable difference between readback and target value.
    readback_signal : Readable, optional
        Signal to read back (defaults to set_signal).
    plan : Callable[..., MsgGenerator], optional
        Plan to run between checks (defaults to sleep).
    plan_parm : Sequence, optional
        Parameters for the plan (defaults to [1]).
    final_plan : MsgGenerator, optional
        Plan to run after tolerance is reached (defaults to set_setpoint_to_readback).

    Returns
    -------
    MsgGenerator
        Bluesky plan generator.
    """
    if plan is None:
        plan = sleep
    if plan_parm is None:
        plan_parm = [1]
    if readback_signal is None:
        readback_signal = set_signal
    if final_plan is None:
        final_plan = set_setpoint_to_readback(set_signal, readback_signal)

    yield from abs_set(set_signal, value, wait=False)

    def inner_plan() -> MsgGenerator:
        while True:
            readback = yield from bps.rd(readback_signal)
            if abs(readback - value) <= tolerance:
                break
            yield from plan(*plan_parm)
            yield from bps.checkpoint()

    yield from bpp.finalize_wrapper(
        plan=inner_plan(),
        final_plan=final_plan,
    )
