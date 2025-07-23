from collections import defaultdict
from unittest.mock import AsyncMock

import pytest
from bluesky.protocols import Reading
from bluesky.run_engine import RunEngine
from dodal.devices.temperture_controller import Lakeshore340
from ophyd_async.core import init_devices

from sm_bluesky.common.plan_stubs.set_and_do_other_plan import (
    set_and_wait_within_tolerance,
)


@pytest.fixture
async def sim_lakeshore():
    async with init_devices(mock=True):
        sim_lakeshore = Lakeshore340("BL007")

    return sim_lakeshore


async def test_set_and_wait_within_tolerance(
    sim_lakeshore: Lakeshore340, RE: RunEngine
):
    docs = defaultdict(list)

    def capture_emitted(name, doc):
        docs[name].append(doc)

    sim_lakeshore.temperature.user_readback[1].read = AsyncMock()
    sim_lakeshore.temperature.user_readback[1].read.side_effect = [
        Reading(value={"value": i})  # type: ignore
        for i in range(0, 200)
    ]

    RE(
        set_and_wait_within_tolerance(
            set_signal=sim_lakeshore.temperature.user_setpoint[1],
            value=10,
            readback_signal=sim_lakeshore.temperature.user_readback[1],
            tolerance=0.1,
        ),
        capture_emitted,
    )
    assert sim_lakeshore.temperature.user_readback[1].read.call_count == 10 + 2
