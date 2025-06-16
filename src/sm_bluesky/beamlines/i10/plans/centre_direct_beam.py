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
    mirror_start: float = 4.8,
    mirror_end: float = 5.2,
    mirror_num: int = 100,
    sy_start: float = -0.25,
    sy_end: float = 0.25,
    sy_num: int = 50,
    pin_half_cut: float = 1.0,
) -> MsgGenerator:
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
    yield from step_scan_and_move_fit(
        det=det,
        motor=sample_stage().y,
        start=sy_start,
        end=sy_end,
        num=sy_num,
        detname_suffix=det_name,
        fitted_loc=StatPosition.D_CEN,
    )


def beam_on_centre_diffractometer(
    det: StandardReadable = RASOR_DEFAULT_DET,
    det_name: str = RASOR_DEFAULT_DET_NAME_EXTENSION,
) -> MsgGenerator:
    """Move the pin hole to the centre of the beam."""
    yield from move_pin_origin()
    yield from bps.abs_set(sample_stage().y, -2.0, wait=True)
    yield from centre_det_angles(det, det_name)
    yield from beam_on_pin(det, det_name)
    y_0 = yield from bps.rd(sample_stage().y)
    yield from bps.abs_set(diffractometer().th, 180, wait=True)
    yield from move_pin_origin()
    y_180 = yield from bps.rd(sample_stage().y)
    middle_y = (y_180 + y_0) / 2.0
    while abs(middle_y - y_180) > 0.08:
        yield from bps.rel_set(focusing_mirror().y, 0.001 * middle_y, wait=True)
        yield from beam_on_pin(det, det_name)
        y_180 = yield from bps.rd(sample_stage().y)
    yield from bps.abs_set(diffractometer().th, 0, wait=True)
