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
from ophyd_async.core import DeviceVector, get_mock_put, init_devices
from ophyd_async.epics.core import epics_signal_r
from ophyd_async.sim import SimMotor

from sm_bluesky.beamlines.i06_1.plans import fastfieldscan

MOCK_AXIS_STEPS = 10


@pytest.fixture
def scmc_psu() -> ThreeMagnetAxisPowerSupply:
    with init_devices(mock=True):
        scmc_psu = ThreeMagnetAxisPowerSupply("TEST:")
    return scmc_psu


@pytest.fixture
async def scmc(scmc_psu: ThreeMagnetAxisPowerSupply) -> SuperConductingMagnetController:
    scmc = SuperConductingMagnetController("TEST", scmc_psu, name="scmc")
    await scmc.connect(
        mock=MockSuperConductingMagnetController(steps=MOCK_AXIS_STEPS, ramp_time=1)
    )
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


async def test_fastfieldscan(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    scmc: SuperConductingMagnetController,
    scaler_controller: ScalerCardController,
    scaler_mag: ScalerCard,
) -> None:
    run_engine(bps.mv(scmc.mode, MagnetMode.UNIAXIAL_X))

    start_field = 0
    end_field = 1
    integration_time = 1
    ramp_rate = 2

    run_engine(
        fastfieldscan(
            scmc.cart.x,
            start_field=start_field,
            stop_field=end_field,
            field_ramp_rate=ramp_rate,
            integration_time=integration_time,
            detectors=[],
            scaler_card=scaler_mag,
        )
    )
    positions = [
        event["data"]["scmc-cart-x"] for event in run_engine_documents["event"]
    ]
    assert sorted(set(positions)) == pytest.approx(
        [
            start_field + (end_field - start_field) * i / MOCK_AXIS_STEPS
            for i in range(1, MOCK_AXIS_STEPS + 1)
        ]
    )
    # Check final position
    assert await scmc.cart.x.readback.get_value() == pytest.approx(end_field)
    get_mock_put(scmc.cart.x.psu_ref().ramp_rate.demand).assert_called_once_with(
        ramp_rate
    )
    get_mock_put(scaler_controller.integration_time).assert_called_once_with(
        integration_time
    )
