from collections.abc import Iterable, Sequence
from typing import Any

from bluesky.plans import count, grid_scan, scan
from bluesky.protocols import Movable, Readable
from bluesky.utils import (
    CustomPlanMetadata,
    MsgGenerator,
    ScalarOrIterableFloat,
    plan,
)
from dodal.devices.electron_analyser.base import (
    AbstractBaseSequence,
    ElectronAnalyserDetector,
)

from sm_bluesky.electron_analyser.plan_stubs.analyser_per_step import (
    analyser_nd_step,
    analyser_shot,
)
from sm_bluesky.electron_analyser.plan_stubs.wrapped import dict_to_sequence


def analysercount(
    analyser: ElectronAnalyserDetector,
    sequence: AbstractBaseSequence,
    detectors: Sequence[Readable],
    num: int = 1,
    delay: ScalarOrIterableFloat = 0.0,
    *,
    md: CustomPlanMetadata | None = None,
) -> MsgGenerator:
    reg_detectors = analyser.create_region_detector_list(sequence.get_enabled_regions())
    yield from count(
        reg_detectors + list(detectors),
        num,
        delay,
        per_shot=analyser_shot,
        md=md,
    )


@plan
def analyserscan(
    analyser: ElectronAnalyserDetector,
    sequence: AbstractBaseSequence | dict[str, Any],
    detectors: Sequence[Readable],
    args: Sequence[Movable | Any],
    num: int | None = None,
    md: CustomPlanMetadata | None = None,
) -> MsgGenerator:

    if isinstance(sequence, dict):
        sequence = dict_to_sequence(analyser, sequence)
    reg_detectors = analyser.create_region_detector_list(sequence.get_enabled_regions())
    yield from scan(
        reg_detectors + list(detectors),
        *args,
        num,
        per_step=analyser_nd_step,
        md=md,
    )


@plan
def grid_analyserscan(
    analyser: ElectronAnalyserDetector,
    sequence: AbstractBaseSequence,
    detectors: Sequence[Readable],
    args: Sequence[Movable | Any],
    snake_axes: Iterable | bool | None = None,
    md: CustomPlanMetadata | None = None,
) -> MsgGenerator:
    if isinstance(sequence, dict):
        sequence = dict_to_sequence(analyser, sequence)
    reg_detectors = analyser.create_region_detector_list(sequence.get_enabled_regions())
    yield from grid_scan(
        reg_detectors + list(detectors),
        *args,
        snake_axes=snake_axes,
        per_step=analyser_nd_step,
        md=md,
    )
