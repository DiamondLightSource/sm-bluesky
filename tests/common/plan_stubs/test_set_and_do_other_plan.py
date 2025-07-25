from collections import defaultdict
from unittest.mock import AsyncMock

from bluesky.plans import count
from bluesky.protocols import Reading
from bluesky.run_engine import RunEngine
from dodal.devices.motors import XYZStage
from ophyd_async.testing import assert_emitted

from sm_bluesky.common.plan_stubs.set_and_do_other_plan import (
    set_and_wait_within_tolerance,
)


async def test_set_and_wait_within_tolerance(sim_motor: XYZStage, RE: RunEngine):
    docs = defaultdict(list)

    def capture_emitted(name, doc):
        docs[name].append(doc)

    sim_motor.x.user_readback.read = AsyncMock()
    sim_motor.x.user_readback.read.side_effect = [
        Reading(value={"value": i})  # type: ignore
        for i in range(0, 200)
    ]

    RE(
        set_and_wait_within_tolerance(
            set_signal=sim_motor.x.user_setpoint,
            value=10,
            readback_signal=sim_motor.x.user_readback,
            tolerance=0.1,
            time=0.0,
        ),
        capture_emitted,
    )
    assert sim_motor.x.user_readback.read.call_count == 10 + 2


async def test_set_and_wait_within_tolerance_with_count_kwargs(
    sim_motor: XYZStage, RE: RunEngine
):
    docs = defaultdict(list)

    def capture_emitted(name, doc):
        docs[name].append(doc)

    sim_motor.x.user_readback.read = AsyncMock()
    sim_motor.x.user_readback.read.side_effect = [
        Reading(value={"value": i})  # type: ignore
        for i in range(0, 200)
    ]
    setpoint = 10
    RE(
        set_and_wait_within_tolerance(
            set_signal=sim_motor.x.user_setpoint,
            value=setpoint,
            readback_signal=sim_motor.x.user_readback,
            tolerance=0.1,
            plan=count,
            detectors=[sim_motor],
            num=2,
        ),
        capture_emitted,
    )
    assert sim_motor.x.user_readback.read.call_count == setpoint + 2
    assert_emitted(
        docs, start=setpoint, descriptor=setpoint, event=setpoint * 2, stop=setpoint
    )


async def test_set_and_wait_within_tolerance_with_count(
    sim_motor: XYZStage, RE: RunEngine
):
    docs = defaultdict(list)

    def capture_emitted(name, doc):
        docs[name].append(doc)

    sim_motor.x.user_readback.read = AsyncMock()
    sim_motor.x.user_readback.read.side_effect = [
        Reading(value={"value": i})  # type: ignore
        for i in range(0, 200)
    ]
    setpoint = 10
    RE(
        set_and_wait_within_tolerance(
            sim_motor.x.user_setpoint,
            setpoint,
            0.1,
            sim_motor.x.user_readback,
            count,
            None,
            [sim_motor],
            2,
        ),
        capture_emitted,
    )
    assert sim_motor.x.user_readback.read.call_count == setpoint + 2
    assert_emitted(
        docs, start=setpoint, descriptor=setpoint, event=setpoint * 2, stop=setpoint
    )
