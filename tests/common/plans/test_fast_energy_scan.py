from collections import defaultdict
from pathlib import Path
from unittest.mock import ANY

import pytest
from bluesky.protocols import Readable
from bluesky.run_engine import RunEngine
from daq_config_server.client import ConfigServer
from dodal.devices.beamlines.i10.i10_apple2 import (
    I10Apple2,
    I10Apple2Controller,
)
from dodal.devices.insertion_device import (
    BeamEnergy,
    InsertionDeviceEnergy,
    UndulatorGap,
    UndulatorJawPhase,
    UndulatorPhaseAxes,
)
from dodal.devices.insertion_device.energy_motor_lookup import (
    ConfigServerEnergyMotorLookup,
)
from dodal.devices.insertion_device.lookup_table_models import (
    LookupTableColumnConfig,
    Source,
)
from dodal.devices.pgm import PlaneGratingMonochromator
from ophyd_async.core import (
    Device,
    StrictEnum,
    init_devices,
    set_mock_value,
)
from ophyd_async.testing import assert_emitted

from sm_bluesky.common.plans import soft_fly_energy_scan
from sm_bluesky.common.sim_devices.sim_stage import SimMotorExtra
from tests.test_data.common import (
    ID_ENERGY_2_GAP_CALIBRATIONS_CSV,
    ID_ENERGY_2_PHASE_CALIBRATIONS_CSV,
)

# add mock_config_client, mock_id_gap, mock_phase and mock_jaw_phase_axes to pytest.
pytest_plugins = ["dodal.testing.fixtures.devices.apple2"]


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

    set_mock_value(mock_pgm.energy.acceleration_time, 0.1)
    set_mock_value(mock_pgm.energy.user_readback, 500)
    set_mock_value(mock_pgm.energy.user_setpoint, 500)
    set_mock_value(mock_pgm.energy.max_velocity, 50)
    set_mock_value(mock_pgm.energy.high_limit_travel, 1700)
    set_mock_value(mock_pgm.energy.low_limit_travel, 400)
    return mock_pgm


@pytest.fixture
async def mock_id(
    mock_id_gap: UndulatorGap,
    mock_phase_axes: UndulatorPhaseAxes,
    mock_jaw_phase: UndulatorJawPhase,
) -> I10Apple2:
    async with init_devices(mock=True):
        mock_id = I10Apple2(
            id_gap=mock_id_gap, id_phase=mock_phase_axes, id_jaw_phase=mock_jaw_phase
        )
    set_mock_value(mock_id.gap().acceleration_time, 0.2)
    set_mock_value(mock_id.gap().velocity, 2)
    set_mock_value(mock_id.gap().max_velocity, 200)
    set_mock_value(mock_id.gap().min_velocity, 0.0)
    return mock_id


@pytest.fixture
def mock_i10_gap_energy_motor_lookup_idu(
    mock_config_client: ConfigServer,
) -> ConfigServerEnergyMotorLookup:
    return ConfigServerEnergyMotorLookup(
        config_client=mock_config_client,
        lut_config=LookupTableColumnConfig(source=Source(column="Source", value="idu")),
        path=Path(ID_ENERGY_2_GAP_CALIBRATIONS_CSV),
    )


@pytest.fixture
def mock_i10_phase_energy_motor_lookup_idu(
    mock_config_client: ConfigServer,
) -> ConfigServerEnergyMotorLookup:
    return ConfigServerEnergyMotorLookup(
        config_client=mock_config_client,
        lut_config=LookupTableColumnConfig(source=Source(column="Source", value="idu")),
        path=Path(ID_ENERGY_2_PHASE_CALIBRATIONS_CSV),
    )


@pytest.fixture
async def mock_id_controller(
    mock_id: I10Apple2,
    mock_i10_gap_energy_motor_lookup_idu: ConfigServerEnergyMotorLookup,
    mock_i10_phase_energy_motor_lookup_idu: ConfigServerEnergyMotorLookup,
) -> I10Apple2Controller:
    async with init_devices(mock=True):
        mock_id_controller = I10Apple2Controller(
            apple2=mock_id,
            gap_energy_motor_lut=mock_i10_gap_energy_motor_lookup_idu,
            phase_energy_motor_lut=mock_i10_phase_energy_motor_lookup_idu,
        )

    return mock_id_controller


@pytest.fixture
async def mock_id_energy(
    mock_id_controller: I10Apple2Controller,
) -> InsertionDeviceEnergy:
    async with init_devices(mock=True):
        mock_id_energy = InsertionDeviceEnergy(id_controller=mock_id_controller)
    return mock_id_energy


@pytest.fixture
async def mock_energy(
    mock_id_energy: InsertionDeviceEnergy, mock_pgm: PlaneGratingMonochromator
) -> BeamEnergy:
    async with init_devices(mock=True):
        mock_energy = BeamEnergy(id_energy=mock_id_energy, mono=mock_pgm.energy)

    return mock_energy


async def test_soft_fly_energy_scan_success(
    mock_energy: BeamEnergy, run_engine: RunEngine, fake_detector: Readable
) -> None:
    docs = defaultdict(list)

    def capture_emitted(name, doc):
        docs[name].append(doc)

    run_engine(
        soft_fly_energy_scan([fake_detector], mock_energy, 700, 800, 0.2, 1e-3),
        capture_emitted,
        wait=True,
    )

    assert_emitted(docs, start=1, descriptor=1, event=ANY, stop=1)
    # Number of event depend how fast motor is moving, it has to be more than 1
    assert len(docs["event"]) > 1
    # check the starting point
    assert docs["event"][0]["data"] == {
        "fake_detector-value": ANY,
        "mock_id_controller-energy": 750.0,
        "mock_pgm-energy": 700.0,
    }
    # check end point
    assert docs["event"][-1]["data"] == {
        "fake_detector-value": ANY,
        "mock_id_controller-energy": 750.0,
        "mock_pgm-energy": 810.0,
    }
    # speed reset
    assert await mock_energy._mono_energy().velocity.get_value() == 1.0
    assert (
        await mock_energy._id_energy()
        ._id_controller()
        .apple2()
        .gap()
        .velocity.get_value()
        == 2.0
    )
