from bluesky.plans import grid_scan
from bluesky.utils import MsgGenerator
from dodal.beamlines.i05 import devices as i05_devices
from dodal.common import inject
from dodal.device_manager import DeviceManager
from dodal.devices.beamlines.i05_shared import PolynomCompoundMotors
from dodal.devices.common_mirror import XYZPiezoSwitchingMirror
from dodal.devices.motors import Motor, XYZPitchYawRollStage
from ophyd_async.core import StandardReadable

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


def align_mirrors_800(
    m1_start: float,
    m1_end: float,
    m1_num: int,
    m3_start: float,
    m3_end: float,
    m3_num: int,
    det: StandardReadable = inject("dj7current_new"),
    m1_pitch: PolynomCompoundMotors = inject("m1es_pitch_800"),
    m3_pitch: Motor = inject("m3mj6_switching_mirror.pitch"),
) -> MsgGenerator:
    """
    Plan to align the M1 and M3 mirrors by scanning the pitch of the mirror and moving
    to the fitted position.

    Parameters
    ----------
    det: StandardReadable,
        Detector to be use for alignment.
    motor: PolynomCompoundMotors
        The compound motor that controls the pitch of the mirror.
    start: float,
        The starting position for the scan.
    end: float,
        The ending position for the scan.
    num: int = 10,
        The number of steps in the scan.
    """

    yield from grid_scan(
        [det],
        m1_pitch,
        m1_start,
        m1_end,
        m1_num,
        m3_pitch,
        m3_start,
        m3_end,
        m3_num,
    )
