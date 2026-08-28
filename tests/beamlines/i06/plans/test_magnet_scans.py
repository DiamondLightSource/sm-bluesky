from collections.abc import Mapping, Sequence
from typing import Any

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
from ophyd_async.core import (
    Device,
    DeviceVector,
    get_mock_put,
    init_devices,
)
from ophyd_async.epics.core import epics_signal_r
from ophyd_async.sim import SimMotor

from sm_bluesky.beamlines.i06_1.plans import fastfieldscan, fastfieldscan_with_energy

MOCK_AXIS_STEPS = 20
EXTRA_METADATA = {"sample_id": "test-sample", "purpose": "magnet-scan"}


def assert_custom_metadata(custom_md: Mapping[str, Any] | None, md: Mapping[str, Any]):
    if custom_md is None:
        return
    for key, value in custom_md.items():
        assert md[key] == value


def assert_base_fastfieldscan_metadata(
    axis: MagnetAxis,
    start_field: float,
    end_field: float,
    field_ramp_rate: float,
    scaler_card: ScalerCard,
    integration_time: float,
    detectors: Sequence[Device],
    metadata: Mapping[str, Any],
):
    assert metadata["plan_args"] == {
        "magnet_axis": axis.name,
        "start_field": start_field,
        "end_field": end_field,
        "field_ramp_rate": field_ramp_rate,
        "scaler_card": scaler_card.name,
        "integration_time": integration_time,
        "detectors": [axis.name, scaler_card.name, *[det.name for det in detectors]],
    }


@pytest.fixture
def scmc_psu() -> ThreeMagnetAxisPowerSupply:
    with init_devices(mock=True):
        scmc_psu = ThreeMagnetAxisPowerSupply("TEST:")
    return scmc_psu


@pytest.fixture
async def scmc_instant(
    scmc_psu: ThreeMagnetAxisPowerSupply,
) -> SuperConductingMagnetController:
    scmc = SuperConductingMagnetController("TEST", scmc_psu, name="scmc")
    await scmc.connect(mock=MockSuperConductingMagnetController(steps=0))
    return scmc


@pytest.fixture
async def scmc(scmc_psu: ThreeMagnetAxisPowerSupply) -> SuperConductingMagnetController:
    scmc = SuperConductingMagnetController("TEST", scmc_psu, name="scmc")
    await scmc.connect(
        mock=MockSuperConductingMagnetController(steps=MOCK_AXIS_STEPS, ramp_time=0.5)
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
def beam_energy() -> Movable[float]:
    with init_devices(mock=True):
        beam_energy = SimMotor(initial_value=599.9, instant=True)
    return beam_energy


@pytest.mark.parametrize(
    "mode", [MagnetMode.UNIAXIAL_X, MagnetMode.UNIAXIAL_Y, MagnetMode.UNIAXIAL_Z]
)
async def test_fastfieldscan_scans_magnet_axis(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    scmc: SuperConductingMagnetController,
    scaler_controller: ScalerCardController,
    scaler_mag: ScalerCard,
    mode: MagnetMode,
) -> None:
    run_engine(bps.mv(scmc.mode, mode))

    mag_axis: MagnetAxis = getattr(scmc.cart, mode.axis_alias)
    start_field = 0.0
    end_field = 1.0
    integration_time = 1.0
    ramp_rate = 2.0

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
        pytest.param(EXTRA_METADATA, id="custom-metadata"),
    ],
)
async def test_fastfieldscan_metadata(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    scmc_instant: SuperConductingMagnetController,
    scaler_mag: ScalerCard,
    custom_md: dict[str, str] | None,
) -> None:
    scmc = scmc_instant
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

    assert_custom_metadata(custom_md, md)


@pytest.mark.parametrize(
    "mode", [MagnetMode.UNIAXIAL_X, MagnetMode.UNIAXIAL_Y, MagnetMode.UNIAXIAL_Z]
)
async def test_fastfieldscan_with_energy(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    scmc: SuperConductingMagnetController,
    scaler_mag: ScalerCard,
    beam_energy: SimMotor,
    mode: MagnetMode,
) -> None:
    run_engine(bps.mv(scmc.mode, mode))

    start_field = 0.0
    end_field = 1.0
    integration_time = 1.0
    ramp_rate = 2.0
    energies = (600, 600.05)
    mag_axis: MagnetAxis = getattr(scmc.cart, mode.axis_alias)

    run_engine(
        fastfieldscan_with_energy(
            mag_axis,
            start_field=start_field,
            stop_field=end_field,
            field_ramp_rate=ramp_rate,
            integration_time=integration_time,
            beam_energy=beam_energy,
            energies=energies,
            detectors=[],
            scaler_card=scaler_mag,
        )
    )
    data = [event["data"] for event in run_engine_documents["event"]]
    magnet_positions = [event[mag_axis.name] for event in data]
    beam_energies = [event["beam_energy"] for event in data]

    # The magnet should start moving from 0 towards 1, rather than jumping
    # straight to the final position.
    assert magnet_positions[0] > start_field
    assert magnet_positions[-1] == pytest.approx(end_field)
    # There must be intermediate magnet positions.
    assert any(start_field < position < end_field for position in magnet_positions)
    # The magnet position must never leave the requested range.
    assert all(start_field <= position <= end_field for position in magnet_positions)

    assert_energy_oscillations(energies, beam_energies)
    # Scaler channels are included in every measurement.
    assert all(
        "scaler_mag-channel-1" in event and "scaler_mag-channel-2" in event
        for event in data
    )


def assert_energy_oscillations(
    energies: tuple[float, float],
    beam_energies: list[float],
) -> None:
    print(energies)
    min_energy = min(energies)
    max_energy = max(energies)
    # Never leave the requested range.
    assert all(min_energy <= energy <= max_energy for energy in beam_energies)
    # Must reach both requested energies.
    assert min(beam_energies) == pytest.approx(min_energy)
    assert max(beam_energies) == pytest.approx(max_energy)
    # Determine the direction of each actual movement.
    directions = []
    for previous, current in zip(beam_energies, beam_energies[1:], strict=False):
        if current > previous:
            directions.append("up")
        elif current < previous:
            directions.append("down")

    # Collapse consecutive movements in the same direction.
    direction_changes = [
        direction
        for i, direction in enumerate(directions)
        if i == 0 or direction != directions[i - 1]
    ]
    # We should move up/down/up/down (or down/up/down/up).
    assert len(direction_changes) >= 2
    assert all(
        direction_changes[i] != direction_changes[i - 1]
        for i in range(1, len(direction_changes))
    )


@pytest.mark.parametrize(
    "custom_md",
    [
        pytest.param(None, id="default-metadata"),
        pytest.param(EXTRA_METADATA, id="custom-metadata"),
    ],
)
async def test_fastfieldscan_with_energy_metadata(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    scmc_instant: SuperConductingMagnetController,
    scaler_mag: ScalerCard,
    beam_energy: SimMotor,
    custom_md: dict[str, str] | None,
) -> None:
    scmc = scmc_instant
    run_engine(bps.mv(scmc.mode, MagnetMode.UNIAXIAL_X))

    start_field = 0.0
    end_field = 1.0
    integration_time = 1.0
    ramp_rate = 2.0
    energies = (600, 600.05)

    run_engine(
        fastfieldscan_with_energy(
            scmc.cart.x,
            start_field=start_field,
            stop_field=end_field,
            field_ramp_rate=ramp_rate,
            integration_time=integration_time,
            beam_energy=beam_energy,
            energies=energies,
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
        "detectors": [scmc.cart.x.name, scaler_mag.name, beam_energy.name],
        "beam_energy": beam_energy.name,
        "energies": energies,
    }
    assert md["plan_name"] == "fastfieldscan_with_energy"

    assert_custom_metadata(custom_md, md)
