from collections.abc import Iterable, Sequence
from typing import Any

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
    """
    Check for instance of ElectronAnalyserDetector in the detector list. Provide it with
    sequence file to read and create list of ElectronAnalyserRegionDetector's. Replace
    ElectronAnalyserDetector in list of detectors with the
    list[ElectronAnalyserRegionDetector] and flatten.

    Args:
        detectors:
            Devices to measure with for a scan.
        sequence_file:
            The file to read to create list[ElectronAnalyserRegionDetector].

    Returns:
        list of detectors, with any instances of ElectronAnalyserDetector replaced by
        ElectronAnalyserRegionDetector by the number of regions in the sequence file.

    """
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
    *args: Movable | Any,
    num: int | None = None,
    per_step: PerStep | None = None,
    md: CustomPlanMetadata | None = None,
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
    snake_axes: Iterable | bool | None = None,
    md: CustomPlanMetadata | None = None,
) -> MsgGenerator:
    yield from grid_scan(
        process_detectors_for_analyserscan(detectors, sequence_file),
        *args,
        snake_axes=snake_axes,
        per_step=analyser_nd_step,
        md=md,
    )
