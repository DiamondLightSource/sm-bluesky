from bluesky.plans import grid_scan
from bluesky.utils import MsgGenerator
from dodal.beamlines.i05 import devices as i05_devices
from dodal.common import inject
from dodal.device_manager import DeviceManager
from dodal.devices.beamlines.i05_shared import Grating, PolynomCompoundMotors
from dodal.devices.common_mirror import XYZPiezoSwitchingMirror
from dodal.devices.motors import XYZPitchYawRollStage
from dodal.devices.pgm import PlaneGratingMonochromator
from ophyd_async.core import StandardReadable, StrictEnum

from sm_bluesky.beamlines.i05.configuration.constants import (
    M3MJ6_PITCH_OFFSET_800,
    M3MJ6_PITCH_OFFSET_1600,
    M3MJ6_X_OFFSET_800,
    M3MJ6_X_OFFSET_1600,
)

# Define alignment devices and factory functions to create them.
alignment_devices = DeviceManager()


@alignment_devices.factory()
def m1es_pitch_800(
    m1_collimating_mirror: XYZPitchYawRollStage,
    m3mj6_switching_mirror: XYZPiezoSwitchingMirror,
) -> PolynomCompoundMotors:
    return PolynomCompoundMotors(
        m1_collimating_mirror.pitch,
        {
            m3mj6_switching_mirror.x: M3MJ6_X_OFFSET_800,
            m3mj6_switching_mirror.pitch: M3MJ6_PITCH_OFFSET_800,
        },
    )


@alignment_devices.factory()
def m1es_pitch_1600(
    m1_collimating_mirror: XYZPitchYawRollStage,
    m3mj6_switching_mirror: XYZPiezoSwitchingMirror,
) -> PolynomCompoundMotors:
    return PolynomCompoundMotors(
        m1_collimating_mirror.pitch,
        {
            m3mj6_switching_mirror.x: M3MJ6_X_OFFSET_1600,
            m3mj6_switching_mirror.pitch: M3MJ6_PITCH_OFFSET_1600,
        },
    )


i05_devices.include(alignment_devices)


def map_m1_m3_mirrors_800(
    m1_start: float,
    m1_end: float,
    m1_num: int,
    m3_start: float,
    m3_end: float,
    m3_num: int,
    det: StandardReadable = inject("dj7current_new"),
    m3: XYZPiezoSwitchingMirror = inject("m3mj6_switching_mirror"),
) -> MsgGenerator:
    """
    Plan to find optimal alignment of the M1.pitch and M3MJ6.pitch mirrors
    """
    if get_pgm_grating() == Grating.PT_800:
        m1_pitch = inject("m1es_pitch_800")
    elif get_pgm_grating() == Grating.C_1600:
        m1_pitch = inject("m1es_pitch_1600")
    else:
        raise ValueError("Unsupported grating for M1-M3 alignment.")
    yield from grid_scan(
        [det],
        m1_pitch,
        m1_start,
        m1_end,
        m1_num,
        m3.pitch,
        m3_start,
        m3_end,
        m3_num,
    )


async def get_pgm_grating(
    pgm: PlaneGratingMonochromator = inject("pgm"),
) -> StrictEnum:
    reading = await pgm.grating.get_value()
    return reading
