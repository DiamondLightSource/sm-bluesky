from collections.abc import Iterable, Sequence
from typing import Any

from bluesky.plan_stubs import mv
from bluesky.plans import count, grid_scan, scan
from bluesky.protocols import Movable, Readable
from bluesky.utils import (
    CustomPlanMetadata,
    MsgGenerator,
    ScalarOrIterableFloat,
    plan,
)
from dodal.devices.electron_analyser.base import ElectronAnalyserDetector

from sm_bluesky.electron_analyser.plan_stubs import (
    analyser_nd_step,
    analyser_shot,
)


def analysercount(
    analyser: ElectronAnalyserDetector,
    sequence_file: str,
    detectors: Sequence[Readable],
    num: int = 1,
    delay: ScalarOrIterableFloat = 0.0,
    *,
    md: CustomPlanMetadata | None = None,
) -> MsgGenerator:
    yield from mv(analyser.sequence_loader, sequence_file)
    yield from count(
        list(detectors) + [analyser],
        num,
        delay,
        per_shot=analyser_shot,
        md=md,
    )


@plan
def analyserscan(
    analyser: ElectronAnalyserDetector,
    sequence_file: str,
    detectors: Sequence[Readable],
    *args: Movable | Any,
    num: int | None = None,
    md: CustomPlanMetadata | None = None,
) -> MsgGenerator:
    yield from mv(analyser.sequence_loader, sequence_file)
    yield from scan(
        list(detectors) + [analyser],
        *args,
        num,
        per_step=analyser_nd_step,
        md=md,
    )


@plan
def grid_analyserscan(
    analyser: ElectronAnalyserDetector,
    sequence_file: str,
    detectors: Sequence[Readable],
    *args,
    snake_axes: Iterable | bool | None = None,
    md: CustomPlanMetadata | None = None,
) -> MsgGenerator:
    yield from mv(analyser.sequence_loader, sequence_file)
    yield from grid_scan(
        list(detectors) + [analyser],
        *args,
        snake_axes=snake_axes,
        per_step=analyser_nd_step,
        md=md,
    )
