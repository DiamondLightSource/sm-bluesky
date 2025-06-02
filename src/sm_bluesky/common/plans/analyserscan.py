from collections.abc import Iterable, Sequence
from typing import Any, Optional, Union

from bluesky.plans import PerStep, grid_scan, scan
from bluesky.protocols import (
    Movable,
    Readable,
)
from bluesky.utils import (
    CustomPlanMetadata,
    MsgGenerator,
    plan,
)
from dodal.devices.electron_analyser import (
    ElectronAnalyserDetector,
)

from sm_bluesky.common.plan_stubs import analyser_nd_step


def process_detectors_for_analyserscan(
    detectors: Sequence[Readable],
    sequence_file: str,
) -> Sequence[Readable]:
    # Check for analyser detector. Read in sequence file and replace it with the region
    # detectors
    analyser_detector = None
    region_detectors = []
    for det in detectors:
        if isinstance(det, ElectronAnalyserDetector):
            analyser_detector = det
            region_detectors = det.create_region_detector_list(sequence_file)
            break

    expansions = (
        region_detectors if e == analyser_detector else [e] for e in detectors
    )
    return [v for vals in expansions for v in vals]


@plan
def analyserscan(
    detectors: Sequence[Readable],
    sequence_file: str,
    *args: Union[Movable, Any],
    num: Optional[int] = None,
    per_step: Optional[PerStep] = None,
    md: Optional[CustomPlanMetadata] = None,
) -> MsgGenerator:
    yield from scan(
        process_detectors_for_analyserscan(detectors, sequence_file),
        *args,
        num,
        per_step=analyser_nd_step,
        md=md,
    )


@plan
def grid_analyserscan(
    detectors: Sequence[Readable],
    sequence_file: str,
    *args,
    snake_axes: Optional[Union[Iterable, bool]] = None,
    md: Optional[CustomPlanMetadata] = None,
) -> MsgGenerator:
    yield from grid_scan(
        process_detectors_for_analyserscan(detectors, sequence_file),
        *args,
        snake_axes=snake_axes,
        per_step=analyser_nd_step,
        md=md,
    )
