from collections.abc import Mapping
from unittest.mock import AsyncMock

import pytest
from bluesky.plans import count
from bluesky.protocols import Location, Reading
from bluesky.run_engine import RunEngine
from dodal.devices.motors import XYZStage
from ophyd_async.core import SignalRW, init_devices
from ophyd_async.epics.core import epics_signal_rw
from ophyd_async.testing import assert_emitted

from sm_bluesky.common.plan_stubs.set_and_do_other_plan import (
    set_and_wait_within_tolerance,
)


@pytest.fixture
async def sim_rw_signal() -> SignalRW[float]:
    async with init_devices(mock=True):
        sim_rw_signal = epics_signal_rw(float, read_pv="BL007", write_pv="write")
    return sim_rw_signal


async def test_set_and_wait_within_tolerance(
    sim_motor: XYZStage,
    run_engine: RunEngine,
) -> None:
    sim_motor.x.user_readback.read = AsyncMock()
    sim_motor.x.user_readback.read.side_effect = [
        Reading(value={"value": i})  # type: ignore
        for i in range(0, 200)
    ]

    run_engine(
        set_and_wait_within_tolerance(
            set_signal=sim_motor.x.user_setpoint,
            value=10,
            readback_signal=sim_motor.x.user_readback,
            tolerance=0.1,
            time=0.0,
        ),
    )
    assert sim_motor.x.user_readback.read.call_count == 10 + 2


async def test_set_and_wait_within_tolerance_with_count_kwargs(
    sim_motor: XYZStage,
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
) -> None:
    sim_motor.x.user_readback.read = AsyncMock()
    sim_motor.x.user_readback.read.side_effect = [
        Reading(value={"value": i})  # type: ignore
        for i in range(0, 200)
    ]
    setpoint = 10
    run_engine(
        set_and_wait_within_tolerance(
            set_signal=sim_motor.x.user_setpoint,
            value=setpoint,
            readback_signal=sim_motor.x.user_readback,
            tolerance=0.1,
            plan=count,
            detectors=[sim_motor],
            num=2,
        ),
    )
    assert sim_motor.x.user_readback.read.call_count == setpoint + 2
    assert_emitted(
        run_engine_documents,
        start=setpoint,
        descriptor=setpoint,
        event=setpoint * 2,
        stop=setpoint,
    )


async def test_set_and_wait_within_tolerance_with_count(
    sim_motor: XYZStage,
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
) -> None:
    sim_motor.x.user_readback.read = AsyncMock()
    sim_motor.x.user_readback.read.side_effect = [
        Reading(value={"value": i})  # type: ignore
        for i in range(0, 200)
    ]
    setpoint = 10
    run_engine(
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
    )
    assert sim_motor.x.user_readback.read.call_count == setpoint + 2
    assert_emitted(
        run_engine_documents,
        start=setpoint,
        descriptor=setpoint,
        event=setpoint * 2,
        stop=setpoint,
    )


async def test_set_and_wait_within_tolerance_without_readback(
    sim_rw_signal: SignalRW[float],
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
) -> None:
    setpoint = 10
    sim_rw_signal.locate = AsyncMock()
    sim_rw_signal.locate.side_effect = [
        Location(setpoint=setpoint, readback=i)  # type: ignore
        for i in range(0, 200)
    ]

    run_engine(
        set_and_wait_within_tolerance(
            set_signal=sim_rw_signal,
            value=setpoint,
            tolerance=0.1,
            plan=count,
            detectors=[sim_rw_signal],
            num=2,
        ),
    )
    assert sim_rw_signal.locate.call_count == setpoint + 2
    assert_emitted(
        run_engine_documents,
        start=setpoint,
        descriptor=setpoint,
        event=setpoint * 2,
        stop=setpoint,
    )
