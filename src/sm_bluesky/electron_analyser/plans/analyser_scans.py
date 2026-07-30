from collections.abc import Iterable, Sequence

from bluesky.plans import count, grid_scan, scan
from bluesky.protocols import Movable, Readable
from bluesky.utils import (
    CustomPlanMetadata,
    MsgGenerator,
    ScalarOrIterableFloat,
    plan,
)
from dodal.devices.electron_analyser.base import BaseSequence, ElectronAnalyserDetector
from dodal.devices.fast_shutter import GenericFastShutter

from sm_bluesky.electron_analyser.plan_stubs.analyser_per_step import (
    make_analyser_per_shot,
    make_analyser_per_step,
)


def analysercount(
    analyser: ElectronAnalyserDetector,
    sequence: BaseSequence,
    detectors: Sequence[Readable],
    num: int = 1,
    delay: ScalarOrIterableFloat = 0.0,
    shutter: GenericFastShutter | None = None,
    close_shutter_per_region: bool = False,
    *,
    md: CustomPlanMetadata | None = None,
) -> MsgGenerator:
    """
    Count with an electron analyser, collecting each enabled region separately.

    The analyser is configured for each enabled region in the sequence and the
    provided detectors are triggered and read for each region. An optional shutter
    can be opened for each region and closed after each region if requested.

    Parameters
    ----------
    analyser:
        Electron analyser to configure and measure with.
    sequence:
        Sequence containing the analyser regions to collect.
    detectors:
        Additional detectors to trigger and read for each region.
    num:
        Number of readings to acquire.
    delay:
        Time delay between readings.
    shutter:
        Optional shutter to open before collecting each region.
    close_shutter_per_region:
        Whether to close the shutter after collecting each region.
    md:
        Additional metadata to include in the run.
    """
    per_shot = make_analyser_per_shot(
        analyser, sequence, close_shutter_per_region, shutter
    )
    yield from count(
        [*detectors, analyser],
        num=num,
        delay=delay,
        per_shot=per_shot,
        md=md,
    )


@plan
def analyserscan(
    analyser: ElectronAnalyserDetector,
    sequence: BaseSequence,
    detectors: Sequence[Readable],
    args: Sequence[Movable | float | int],
    num: int | None = None,
    shutter: GenericFastShutter | None = None,
    close_shutter_per_region: bool = False,
    *,
    md: CustomPlanMetadata | None = None,
) -> MsgGenerator:
    """
    Perform a scan while collecting each enabled electron analyser region separately.

    At each scan step, the scan motors are moved to their target positions, then
    the analyser is configured for each enabled region in the sequence. The
    provided detectors and analyser are triggered and read for each region.
    An optional shutter can be opened for each region and closed after each region
    if requested.

    Parameters
    ----------
    analyser:
        Electron analyser to configure and measure with.
    sequence:
        Sequence containing the analyser regions to collect.
    detectors:
        Additional detectors to trigger and read for each region.
    args:
        Sequence of scan arguments defining the motors, positions, and number of
        points or intervals.
    num:
        Number of points to acquire at each step.
    shutter:
        Optional shutter to open before collecting each region.
    close_shutter_per_region:
        Whether to close the shutter after collecting each region.
    md:
        Additional metadata to include in the run.
    """
    per_step = make_analyser_per_step(
        analyser, sequence, close_shutter_per_region, shutter
    )
    yield from scan(
        [*detectors, analyser],
        *args,
        num=num,
        per_step=per_step,
        md=md,
    )


@plan
def grid_analyserscan(
    analyser: ElectronAnalyserDetector,
    sequence: BaseSequence,
    detectors: Sequence[Readable],
    args: Sequence[Movable | float | int],
    shutter: GenericFastShutter | None = None,
    close_shutter_per_region: bool = False,
    snake_axes: Iterable | bool | None = None,
    *,
    md: CustomPlanMetadata | None = None,
) -> MsgGenerator:
    """
    Perform a grid scan while collecting each enabled electron analyser region
    separately.

    At each grid scan step, the scan motors are moved to their target positions,
    then the analyser is configured for each enabled region in the sequence. The
    provided detectors and analyser are triggered and read for each region.
    An optional shutter can be opened for each region and closed after each region
    if requested.

    Parameters
    ----------
    analyser:
        Electron analyser to configure and measure with.
    sequence:
        Sequence containing the analyser regions to collect.
    detectors:
        Additional detectors to trigger and read for each region.
    args:
        Sequence of grid scan arguments defining the motors, positions, and
        number of points or intervals.
    shutter:
        Optional shutter to open before collecting each region.
    close_shutter_per_region:
        Whether to close the shutter after collecting each region.
    snake_axes:
        Whether to reverse the direction of alternating axes for each row of
        the grid scan.
    md:
        Additional metadata to include in the run.
    """
    per_step = make_analyser_per_step(
        analyser, sequence, close_shutter_per_region, shutter
    )
    yield from grid_scan(
        [*detectors, analyser],
        *args,
        snake_axes=snake_axes,
        per_step=per_step,
        md=md,
    )
