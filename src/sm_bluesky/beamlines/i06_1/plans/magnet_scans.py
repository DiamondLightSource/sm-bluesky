from collections.abc import Sequence

import bluesky.preprocessors as bpp
from bluesky import plan_stubs as bps
from bluesky.protocols import Movable, Readable
from bluesky.utils import CustomPlanMetadata, MsgGenerator, plan
from dodal.common.coordination import inject
from dodal.devices.beamlines.i06_1.magnet import FlyMagnetInfo, MagnetAxis
from dodal.devices.scaler_card import ScalerCard

from sm_bluesky.common.helper.utils import deep_update, unique_objs
from sm_bluesky.common.plan_stubs.detection import fly_kickoff_complete


def _raw_fastfieldscan(
    magnet_axis: MagnetAxis,
    mag_fly_info: FlyMagnetInfo,
    detectors: Sequence[Readable],
    scaler_card: ScalerCard,
    integration_time: float | None = None,
    md: CustomPlanMetadata | None = None,
    trigger_and_read: bps.TakeReading | None = None,
) -> MsgGenerator:
    """Execute the common setup and fly-scan sequence for a magnetic field scan.

    Stages the supplied detectors, prepares the magnet axis for the requested
    fly scan, configures the scaler integration time, and performs the fly
    scan. An optional trigger-and-read plan can be supplied to customise the
    acquisition performed during the fly.

    Args:
        magnet_axis: Superconducting magnet axis to fly.
        mag_fly_info: Fly scan parameters defining the magnet start position,
            end position, and ramp rate.
        scaler_card: Scaler card used for data acquisition.
        integration_time: Scaler integration time in seconds.
        detectors: Devices to stage and read during the scan.
        md: Metadata to attach to the Bluesky run.
        trigger_and_read: Optional plan used instead of the standard
            trigger-and-read operation during the fly.
    """
    _md = {
        "plan_args": {
            "magnet_axis": magnet_axis.name,
            "start_field": mag_fly_info.start_position,
            "end_field": mag_fly_info.end_position,
            "field_ramp_rate": mag_fly_info.ramp_rate,
            "scaler_card": scaler_card.name,
            "integration_time": integration_time,
            "detectors": [det.name for det in detectors],
        }
    }
    deep_update(_md, md or {})

    @bpp.stage_decorator(detectors)
    @bpp.run_decorator(md=_md)
    def _inner():
        yield from bps.prepare(magnet_axis, mag_fly_info, wait=True)
        if integration_time is not None:
            yield from bps.mv(scaler_card, integration_time)
        yield from fly_kickoff_complete(magnet_axis, detectors, trigger_and_read)

    yield from _inner()


@plan
def fastfieldscan(
    magnet_axis: MagnetAxis,
    start_field: float,
    stop_field: float,
    field_ramp_rate: float,
    detectors: Sequence[Readable],
    integration_time: float | None = None,
    scaler_card: ScalerCard = inject("scaler2_mag"),
    md: CustomPlanMetadata | None = None,
) -> MsgGenerator:
    """Perform a fast fly scan of a superconducting magnet axis.

    The magnet is ramped continuously from ``start_field`` to ``stop_field``
    at the specified field ramp rate while the scaler and requested detectors
    acquire data.

    The magnet axis and scaler card are automatically included in the devices
    staged and read by the scan. Duplicate devices are removed.

    Args:
        magnet_axis: Superconducting magnet axis to scan.
        start_field: Starting magnetic field.
        stop_field: Final magnetic field.
        field_ramp_rate: Rate at which the magnetic field is ramped.
        detectors: Additional detectors to stage and read during the scan.
        integration_time: Optional scaler integration time in seconds. If not provided,
            it will use what is already in EPICS.
        scaler_card: Scaler card used for data acquisition.
        md: Optional metadata to attach to the Bluesky run.

    Yields:
        Bluesky messages implementing the fast field fly scan.
    """
    _md = {"plan_name": "fastfieldscan"}
    _md.update(md or {})
    fly_info = FlyMagnetInfo(
        start_position=start_field, end_position=stop_field, ramp_rate=field_ramp_rate
    )
    yield from _raw_fastfieldscan(
        magnet_axis,
        fly_info,
        unique_objs([magnet_axis, scaler_card, *detectors]),
        scaler_card,
        integration_time,
        _md,
        trigger_and_read=None,
    )


@plan
def fastfieldscan_with_energy(
    magnet_axis: MagnetAxis,
    start_field: float,
    stop_field: float,
    field_ramp_rate: float,
    beam_energy: Movable[float],
    energies: tuple[float, float],
    detectors: Sequence[Readable],
    integration_time: float | None = None,
    scaler_card: ScalerCard = inject("scaler2_mag"),
    md: CustomPlanMetadata | None = None,
) -> MsgGenerator:
    """Perform a fast magnetic field scan while alternating beam energy.

    The magnet is ramped continuously from ``start_field`` to ``stop_field``
    while measurements are performed at each of the requested beam energies.
    For each acquisition point, the beam energy is moved to each value in
    ``energies`` in turn and the detectors are triggered and read.

    The magnet axis and scaler card are automatically included in the devices
    staged and read by the scan. Duplicate devices are removed.

    Args:
        magnet_axis: Superconducting magnet axis to scan.
        start_field: Starting magnetic field.
        stop_field: Final magnetic field.
        field_ramp_rate: Rate at which the magnetic field is ramped.
        energies: Two beam energies to cycle between for each magnetic field
            acquisition.
        beam_energy: Device controlling the beam energy.
        detectors: Additional detectors to stage and read during the scan.
        integration_time: Optional scaler integration time in seconds. If not provided,
            it will use what is already in EPICS.
        scaler_card: Scaler card used for data acquisition.
        md: Optional metadata to attach to the Bluesky run.

    Yields:
        Bluesky messages implementing the fast field fly scan with alternating
        beam energies.
    """
    _md = {
        "plan_name": "fastfieldscan_with_energy",
        "plan_args": {
            "beam_energy": beam_energy.name,  # type: ignore
            "energies": energies,
        },
    }
    _md.update(md or {})

    fly_info = FlyMagnetInfo(
        start_position=start_field, end_position=stop_field, ramp_rate=field_ramp_rate
    )
    # Do long move to set the beam energy to starting position first before scan begins.
    yield from bps.mv(beam_energy, energies[0])

    def _cycle_energies_trigger_read(
        detectors: Sequence[Readable],
    ) -> MsgGenerator:
        for energy in energies:
            yield from bps.mv(beam_energy, energy)
            yield from bps.trigger_and_read(detectors)

    yield from _raw_fastfieldscan(
        magnet_axis,
        fly_info,
        unique_objs([magnet_axis, scaler_card, beam_energy, *detectors]),
        scaler_card,
        integration_time,
        _md,
        trigger_and_read=_cycle_energies_trigger_read,
    )
