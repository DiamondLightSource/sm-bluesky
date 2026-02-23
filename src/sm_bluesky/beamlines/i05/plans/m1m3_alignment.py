from bluesky.plans import grid_scan
from bluesky.utils import MsgGenerator, plan
from dodal.beamlines.i05 import devices as i05_devices
from dodal.common import inject
from dodal.device_manager import DeviceManager
from dodal.devices.beamlines.i05_shared import Grating, PolynomCompoundMotors
from dodal.devices.common_mirror import XYZPiezoSwitchingMirror
from dodal.devices.motors import XYZPitchYawRollStage
from dodal.devices.pgm import PlaneGratingMonochromator
from ophyd_async.core import StandardReadable, StrictEnum

from sm_bluesky.beamlines.i05.configuration.constants import (
    M3MJ6_PITCH_POLY_800,
    M3MJ6_PITCH_POLY_1600,
    M3MJ6_X_POLY_800,
    M3MJ6_X_POLY_1600,
)

# At this point in the alignment, we already have nice parameters for the dependence of
# m3mj6_x, but we want to establish the dependence of m3mj6_pitch vs m1es_pitch.
# The GDA scan command would be something like:
# scan m1es_pitch -200 1600 75 m3mj6_pitch 4750 5350 8 waittime 0.1 dj7current_new
# We then need to fit the peak at each value of m1es_pitch, and from the peak positions
# we fit a third order polynomial. With m1es_pitch then well established, we
# subsequently do the focusing scan using the gas cell.
#
# This scan actually takes over an hour, because the step motion of the hexapod
# (m3mj6_pitch) is slow. In principle we could try to do it in a "fly" mode
# with bluesky, which could be a significant speed up.

# Define alignment devices and factory functions to create them.
alignment_devices = DeviceManager()


# This is a temp polynomial compound motor that maps the m1es_pitch to the already
# defined m3mj6_x for finding m3 pitch dependence on m1es_pitch. Once we have the
# m3mj6_pitch dependence on m1es_pitch, we can then define the real polynomial
# compound motor for m3mj6_pitch and forget this temp one
@alignment_devices.factory()
def m1_m3_x_800(
    m1_collimating_mirror: XYZPitchYawRollStage,
    m3mj6_switching_mirror: XYZPiezoSwitchingMirror,
) -> PolynomCompoundMotors:
    return PolynomCompoundMotors(
        m1_collimating_mirror.pitch,
        {
            m3mj6_switching_mirror.x: M3MJ6_X_POLY_800,
        },
    )


# This is a temp polynomial compound motor that maps the m1es_pitch to the already
# defined m3mj6_x for finding m3 pitch dependence on m1es_pitch. Once we have the
# m3mj6_pitch dependence on m1es_pitch, we can then define the real polynomial
# compound motor for m3mj6_pitch and forget this temp one
@alignment_devices.factory()
def m1_m3_x_1600(
    m1_collimating_mirror: XYZPitchYawRollStage,
    m3mj6_switching_mirror: XYZPiezoSwitchingMirror,
) -> PolynomCompoundMotors:
    return PolynomCompoundMotors(
        m1_collimating_mirror.pitch,
        {
            m3mj6_switching_mirror.x: M3MJ6_X_POLY_1600,
        },
    )


# This is a final polynomial compound motor that maps the m1es_pitch to the
# m3mj6_x for and m3 pitch.
@alignment_devices.factory()
def m1_m3_x_pitch_800(
    m1_collimating_mirror: XYZPitchYawRollStage,
    m3mj6_switching_mirror: XYZPiezoSwitchingMirror,
) -> PolynomCompoundMotors:
    return PolynomCompoundMotors(
        m1_collimating_mirror.pitch,
        {
            m3mj6_switching_mirror.x: M3MJ6_X_POLY_800,
            m3mj6_switching_mirror.pitch: M3MJ6_PITCH_POLY_800,
        },
    )


# This is a final polynomial compound motor that maps the m1es_pitch to the
# m3mj6_x for and m3 pitch.
@alignment_devices.factory()
def m1_m3_x_pitch_1600(
    m1_collimating_mirror: XYZPitchYawRollStage,
    m3mj6_switching_mirror: XYZPiezoSwitchingMirror,
) -> PolynomCompoundMotors:
    return PolynomCompoundMotors(
        m1_collimating_mirror.pitch,
        {
            m3mj6_switching_mirror.x: M3MJ6_X_POLY_1600,
            m3mj6_switching_mirror.pitch: M3MJ6_PITCH_POLY_1600,
        },
    )


i05_devices.include(alignment_devices)


# This will produce 2D map of m1es_pitch vs m3mj6_pitch, with the intensity of
# dj7current_new as the value. We then fit the peak at each value of m1es_pitch,
# and from the peak positions we fit a third order polynomial to find the dependence
# of m3mj6_pitch on m1es_pitch. This will amend M3MJ6_PITCH_POLY_800/1600.
# With m1es_pitch then well established,
# we subsequently do the focusing scan using the gas cell.
@plan
def map_m1_m3_mirrors(
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
        m1_pitch = inject("m1_m3_x_800")
    elif get_pgm_grating() == Grating.C_1600:
        m1_pitch = inject("m1_m3_x_1600")
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
