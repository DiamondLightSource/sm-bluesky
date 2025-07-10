from collections.abc import Hashable

import bluesky.plan_stubs as bps
from bluesky.utils import MsgGenerator, plan
from dodal.beamlines.i10 import diffractometer, focusing_mirror, sample_stage
from ophyd_async.core import StandardReadable

from sm_bluesky.beamlines.i10.configuration.default_setting import (
    RASOR_DEFAULT_DET,
    RASOR_DEFAULT_DET_NAME_EXTENSION,
)
from sm_bluesky.common.plans import StatPosition, step_scan_and_move_fit


@plan
def centre_tth(
    det: StandardReadable = RASOR_DEFAULT_DET,
    det_name: str = RASOR_DEFAULT_DET_NAME_EXTENSION,
    start: float = -1,
    end: float = 1,
    num: int = 21,
) -> MsgGenerator:
    """Centre two theta using Rasor dector."""

    yield from step_scan_and_move_fit(
        det=det,
        motor=diffractometer().tth,
        start=start,
        end=end,
        num=num,
        detname_suffix=det_name,
        fitted_loc=StatPosition.CEN,
    )


@plan
def centre_alpha(
    det: StandardReadable = RASOR_DEFAULT_DET,
    det_name: str = RASOR_DEFAULT_DET_NAME_EXTENSION,
    start: float = -0.8,
    end: float = 0.8,
    num: int = 21,
) -> MsgGenerator:
    """Centre rasor alpha using Rasor dector."""
    yield from step_scan_and_move_fit(
        det=det,
        motor=diffractometer().alpha,
        start=start,
        end=end,
        num=num,
        detname_suffix=det_name,
        fitted_loc=StatPosition.CEN,
    )


@plan
def centre_det_angles(
    det: StandardReadable = RASOR_DEFAULT_DET,
    det_name: str = RASOR_DEFAULT_DET_NAME_EXTENSION,
) -> MsgGenerator:
    """Centre both two theta and alpha angle on Rasor"""
    yield from centre_tth(det, det_name)
    yield from centre_alpha(det, det_name)


def move_pin_origin(wait: bool = True, group: Hashable | None = None) -> MsgGenerator:
    """Move the point to the centre of rotation."""

    if wait and group is None:
        group = "move_pin_origin"
    yield from bps.abs_set(sample_stage().x, 0, wait=False, group=group)
    yield from bps.abs_set(sample_stage().y, 0, wait=False, group=group)
    yield from bps.abs_set(sample_stage().z, 0, wait=False, group=group)
    if wait:
        yield from bps.wait(group=group)


@plan
def beam_on_pin(
    det: StandardReadable = RASOR_DEFAULT_DET,
    det_name: str = RASOR_DEFAULT_DET_NAME_EXTENSION,
    mirror_coverage: float = 0.668,
    mirror_num: int = 51,
    sy_coverage: float = 0.3,
    sy_num: int = 51,
    pin_half_cut: float = 1.0,
) -> MsgGenerator:
    """Move beam onto the pin by scanning
     the focusing mirror and the sample stage in y direction.

    Parameters
    ----------
    det : StandardReadable, optional
        The detector to use for alignment, by default RASOR_DEFAULT_DET
    det_name : str, optional
        The suffix for the detector name, by default RASOR_DEFAULT_DET_NAME_EXTENSION
    mirror_coverage : float, optional
        The coverage of the focusing mirror in fine pitch, by default 0.668
    mirror_num : int, optional
        The number of points to scan for the focusing mirror, by default 51
    sy_coverage : float, optional
        The coverage of the sample stage in y direction in mm, by default 0.3
    sy_num : int, optional
        The number of points to scan for the sample stage in y direction, by default 51
    pin_half_cut : float, optional
        The half cut of the pin in mm, by default 1.0
    """
    mirror_current = yield from bps.rd(focusing_mirror().fine_pitch)
    mirror_start = mirror_current - mirror_coverage / 2.0
    mirror_end = mirror_current + mirror_coverage / 2.0
    yield from bps.abs_set(sample_stage().y, pin_half_cut, wait=True)
    yield from step_scan_and_move_fit(
        det=det,
        motor=focusing_mirror().fine_pitch,
        start=mirror_start,
        end=mirror_end,
        num=mirror_num,
        detname_suffix=det_name,
        fitted_loc=StatPosition.MIN,
    )
    sy_start = pin_half_cut - sy_coverage / 2.0
    sy_end = pin_half_cut + sy_coverage / 2.0
    yield from step_scan_and_move_fit(
        det=det,
        motor=sample_stage().y,
        start=sy_start,
        end=sy_end,
        num=sy_num,
        detname_suffix=det_name,
        fitted_loc=StatPosition.D_CEN,
    )


@plan
def beam_on_centre_diffractometer(
    det: StandardReadable = RASOR_DEFAULT_DET,
    det_name: str = RASOR_DEFAULT_DET_NAME_EXTENSION,
    mirror_height_adjust: float = 0.01,
    mirror_diff_acceptance: float = 0.08,
    pin_clear_beam_position: float = -2.0,
    pin_half_cut: float = 1.0,
) -> MsgGenerator:
    """Move the beam centre of diffractometer by adjusting
     the focusing mirror pitch and height.

    Parameters
    ----------
    det : StandardReadable, optional
        The detector to use for alignment, by default RASOR_DEFAULT_DET
    det_name : str, optional
        The suffix for the detector name, by default RASOR_DEFAULT_DET_NAME_EXTENSION
    mirror_height_adjust : float, optional
        The height adjustment of the focusing mirror in mm, this is  by default 0.01
    mirror_diff_acceptance : float, optional
        The acceptance of the difference between the two y positions in mm,
        by default 0.08
    pin_clear_beam_position : float, optional
        The position of the pin when it is clear of the beam in mm,
        by default -2.0
    pin_half_cut : float, optional
        The half cut of the pin in mm, by default 1.0
    """
    yield from move_pin_origin()
    yield from bps.abs_set(sample_stage().y, pin_clear_beam_position, wait=True)
    yield from centre_det_angles(det, det_name)
    yield from beam_on_pin(det, det_name, pin_half_cut=pin_half_cut)
    y_0 = yield from bps.rd(sample_stage().y)
    yield from bps.abs_set(diffractometer().th, 180, wait=True)
    yield from beam_on_pin(det, det_name, pin_half_cut=y_0)
    y_180 = yield from bps.rd(sample_stage().y)
    middle_y = (y_180 + y_0) / 2.0
    cnt = 0
    while abs(middle_y - y_180) > mirror_diff_acceptance:
        yield from bps.rel_set(
            focusing_mirror().y, mirror_height_adjust * (y_180 - middle_y), wait=True
        )
        yield from beam_on_pin(det, det_name, y_180)
        y_180 = yield from bps.rd(sample_stage().y)
        cnt += 1
        if cnt > 5:
            raise RuntimeError(
                "Failed to centre the pin on the beam after 5 iterations."
            )
    yield from bps.abs_set(diffractometer().th, 0, wait=True)
