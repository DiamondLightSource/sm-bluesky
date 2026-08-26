from collections.abc import Mapping

import pytest
from bluesky import RunEngine
from bluesky import plan_stubs as bps
from bluesky.protocols import Movable
from dodal.devices.beamlines.i06_1.magnet import (
    MagnetAxis,
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
        mock=MockSuperConductingMagnetController(steps=MOCK_AXIS_STEPS, ramp_time=0.1)
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


@pytest.mark.parametrize(
    "axis, mode",
    [
        pytest.param("x", MagnetMode.UNIAXIAL_X, id="x"),
        pytest.param("y", MagnetMode.UNIAXIAL_Y, id="y"),
        pytest.param("z", MagnetMode.UNIAXIAL_Z, id="z"),
    ],
)
async def test_fastfieldscan_scans_magnet_axis(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    scmc: SuperConductingMagnetController,
    scaler_controller: ScalerCardController,
    scaler_mag: ScalerCard,
    axis: str,
    mode: MagnetMode,
) -> None:
    run_engine(bps.mv(scmc.mode, mode))

    start_field = 0
    end_field = 1
    integration_time = 1
    ramp_rate = 2
    mag_axis: MagnetAxis = getattr(scmc.cart, axis)

    run_engine(
        fastfieldscan(
            mag_axis,
            start_field=start_field,
            stop_field=end_field,
            field_ramp_rate=ramp_rate,
            integration_time=integration_time,
            detectors=[],
            scaler_card=scaler_mag,
        )
    )
    mag_axis_values = [
        event["data"][mag_axis.name] for event in run_engine_documents["event"]
    ]
    assert all(start_field <= position <= end_field for position in mag_axis_values)
    assert mag_axis_values == sorted(mag_axis_values)
    unique_positions = sorted(set(mag_axis_values))
    # This asserts that we didn't go to start position to end position instantly and
    # did move to steps between as well.
    assert len(unique_positions) > 2
    assert mag_axis_values[-1] == pytest.approx(end_field)

    get_mock_put(mag_axis.psu_ref().ramp_rate.demand).assert_called_once_with(ramp_rate)
    get_mock_put(scaler_controller.integration_time).assert_called_once_with(
        integration_time
    )


@pytest.mark.parametrize(
    "custom_md",
    [
        pytest.param(None, id="default-metadata"),
        pytest.param(
            {"sample_id": "test-sample", "purpose": "magnet-scan"},
            id="custom-metadata",
        ),
    ],
)
async def test_fastfieldscan_metadata(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    scmc: SuperConductingMagnetController,
    scaler_mag: ScalerCard,
    custom_md: dict[str, str] | None,
) -> None:
    run_engine(bps.mv(scmc.mode, MagnetMode.UNIAXIAL_X))

    start_field = 0.0
    end_field = 1.0
    integration_time = 1.0
    ramp_rate = 2.0

    run_engine(
        fastfieldscan(
            scmc.cart.x,
            start_field=start_field,
            stop_field=end_field,
            field_ramp_rate=ramp_rate,
            integration_time=integration_time,
            detectors=[],
            scaler_card=scaler_mag,
            md=custom_md,
        )
    )
    md = run_engine_documents["start"][0]
    assert md["plan_args"] == {
        "magnet_axis": scmc.cart.x.name,
        "start_field": start_field,
        "end_field": end_field,
        "field_ramp_rate": ramp_rate,
        "scaler_card": scaler_mag.name,
        "integration_time": integration_time,
        "detectors": [scmc.cart.x.name, scaler_mag.name],
    }
    assert md["plan_name"] == "fastfieldscan"

    if custom_md is not None:
        for key, value in custom_md.items():
            assert md[key] == value
