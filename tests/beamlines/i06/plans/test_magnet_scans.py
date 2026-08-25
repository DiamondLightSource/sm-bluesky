from collections.abc import Mapping

import pytest
from bluesky import RunEngine
from bluesky import plan_stubs as bps
from bluesky.protocols import Movable
from dodal.devices.beamlines.i06_1.magnet import (
    MagnetMode,
    SuperConductingMagnetController,
    ThreeMagnetAxisPowerSupply,
)
from dodal.devices.beamlines.i06_1.magnet.superconducting_magnet import (
    MockSuperConductingMagnetController,
)
from dodal.devices.scaler_card import ScalerCard, ScalerCardController
from ophyd_async.core import DeviceVector, init_devices
from ophyd_async.epics.core import epics_signal_r
from ophyd_async.sim import SimMotor

from sm_bluesky.beamlines.i06_1.plans import fastfieldscan


@pytest.fixture
def scmc_psu() -> ThreeMagnetAxisPowerSupply:
    with init_devices(mock=True):
        scmc_psu = ThreeMagnetAxisPowerSupply("TEST:")
    return scmc_psu


@pytest.fixture
async def scmc(scmc_psu: ThreeMagnetAxisPowerSupply) -> SuperConductingMagnetController:
    scmc = SuperConductingMagnetController("TEST", scmc_psu, name="scmc")
    await scmc.connect(mock=MockSuperConductingMagnetController(steps=10, ramp_time=1))
    return scmc


@pytest.fixture
def scaler_controller() -> ScalerCardController:
    with init_devices(mock=True):
        scaler_controller = ScalerCardController("TEST", "", "")
    return scaler_controller


@pytest.fixture
def scaler_mag(scaler_controller: ScalerCardController) -> ScalerCard:
    with init_devices(mock=True):
        scaler_mag = ScalerCard(
            DeviceVector(
                {1: epics_signal_r(float, "1:"), 2: epics_signal_r(float, "2:")}
            ),
            scaler_controller,
        )
    return scaler_mag


@pytest.fixture
def energy() -> Movable[float]:
    with init_devices(mock=True):
        energy = SimMotor()
    return energy


def test_fastfieldscan(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    scmc: SuperConductingMagnetController,
    scaler_mag: ScalerCard,
    energy: Movable[float],
) -> None:
    run_engine(bps.mv(scmc.mode, MagnetMode.UNIAXIAL_X))
    run_engine(fastfieldscan(scmc.cart.x, 0, 1, 2, 1, [], scaler_card=scaler_mag))
