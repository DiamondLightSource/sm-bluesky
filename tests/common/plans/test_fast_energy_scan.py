from collections import defaultdict
from unittest.mock import ANY

import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.apple2_undulator import (
    EnergySetter,
    UndulatorGateStatus,
)
from dodal.devices.i10.i10_apple2 import I10Apple2
from dodal.devices.pgm import PGM
from ophyd_async.core import (
    Device,
    StrictEnum,
    init_devices,
)
from ophyd_async.testing import assert_emitted, set_mock_value

from sm_bluesky.common.plans import soft_fly_energy_scan

from ...sim_devices.sim_stage import SimMotorExtra
from ...test_data.common import (
    LOOKUP_TABLE_PATH,
)


class Grating(StrictEnum):
    TESTING = "Grating"


class FakePGM(Device):
    def __init__(self, name=""):
        self.energy = SimMotorExtra(instant=False)
        super().__init__(name=name)


@pytest.fixture
async def mock_pgm(prefix: str = "BLXX-EA-DET-007:") -> FakePGM:
    async with init_devices(mock=True):
        mock_pgm = FakePGM()
    return mock_pgm


@pytest.fixture
async def mock_energy(mock_pgm: PGM) -> EnergySetter:
    async with init_devices(mock=True):
        mock_energy = EnergySetter(
            id=I10Apple2(
                look_up_table_dir=LOOKUP_TABLE_PATH,
                source=("Source", "idu"),
                prefix="BLWOW-MO-SERVC-01:",
            ),
            pgm=mock_pgm,
        )

    set_mock_value(mock_energy.id.gap.gate, UndulatorGateStatus.CLOSE)
    set_mock_value(mock_energy.id.gap.high_limit_travel, 200)
    set_mock_value(mock_energy.id.gap.low_limit_travel, 10)
    set_mock_value(mock_energy.id.gap.acceleration_time, 0.2)
    set_mock_value(mock_energy.id.phase.gate, UndulatorGateStatus.CLOSE)
    set_mock_value(mock_energy.id.id_jaw_phase.gate, UndulatorGateStatus.CLOSE)
    set_mock_value(mock_energy.id.id_jaw_phase.jaw_phase.velocity, 1)
    set_mock_value(mock_energy.id.gap.velocity, 2)
    set_mock_value(mock_energy.id.gap.max_velocity, 200)
    set_mock_value(mock_energy.id.gap.min_velocity, 0.0)

    set_mock_value(mock_energy.id.phase.btm_inner.velocity, 1)
    set_mock_value(mock_energy.id.phase.top_inner.velocity, 1)
    set_mock_value(mock_energy.id.phase.btm_outer.velocity, 1)
    set_mock_value(mock_energy.id.phase.top_outer.velocity, 1)
    set_mock_value(mock_energy.pgm_ref().energy.acceleration_time, 0.1)
    set_mock_value(mock_energy.pgm_ref().energy.user_readback, 500)
    set_mock_value(mock_energy.pgm_ref().energy.user_setpoint, 500)
    set_mock_value(mock_energy.pgm_ref().energy.max_velocity, 50)
    set_mock_value(mock_energy.pgm_ref().energy.high_limit_travel, 1700)
    set_mock_value(mock_energy.pgm_ref().energy.low_limit_travel, 400)
    return mock_energy


async def test_soft_fly_energy_scan_success(
    mock_energy: EnergySetter, RE: RunEngine, det
):
    docs = defaultdict(list)
    det.start_simulation()

    def capture_emitted(name, doc):
        docs[name].append(doc)

    RE(
        soft_fly_energy_scan([det], mock_energy, 700, 800, 0.2, 1e-3),
        capture_emitted,
        wait=True,
    )

    assert_emitted(docs, start=1, descriptor=1, event=ANY, stop=1)
    # Number of event depend how fast motor is moving, it has to be more than 1
    assert len(docs["event"]) > 1
    # check the starting point
    assert docs["event"][0]["data"] == {
        "rand": ANY,
        "mock_energy-id-energy": 750,
        "mock_pgm-energy": 700.0,
    }
    # check end point
    assert docs["event"][-1]["data"] == {
        "rand": ANY,
        "mock_energy-id-energy": 750,
        "mock_pgm-energy": 810.0,
    }
    # speed reset
    assert await mock_energy.pgm_ref().energy.velocity.get_value() == 1.0
    assert await mock_energy.id.gap.velocity.get_value() == 2.0
