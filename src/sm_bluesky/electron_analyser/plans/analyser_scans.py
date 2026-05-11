from collections.abc import Iterable, Sequence

from bluesky.plan_stubs import prepare
from bluesky.plans import count, grid_scan, scan
from bluesky.protocols import Movable, Readable
from bluesky.utils import (
    CustomPlanMetadata,
    MsgGenerator,
    ScalarOrIterableFloat,
    plan,
)
from dodal.devices.electron_analyser.base import (
    BaseSequence,
    ElectronAnalyserDetector,
)

from sm_bluesky.electron_analyser.plan_stubs import (
    analyser_nd_step,
    analyser_shot,
)


def analysercount(
    analyser: ElectronAnalyserDetector,
    region: BaseSequence,
    detectors: Sequence[Readable],
    num: int = 1,
    delay: ScalarOrIterableFloat = 0.0,
    *,
    md: CustomPlanMetadata | None = None,
) -> MsgGenerator:
    yield from prepare(analyser.sequence, region)
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
    sequence: BaseSequence,
    detectors: Sequence[Readable],
    args: Sequence[Movable | float | int],
    num: int | None = None,
    md: CustomPlanMetadata | None = None,
) -> MsgGenerator:
    yield from prepare(analyser.sequence, sequence)
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
    sequence: BaseSequence,
    detectors: Sequence[Readable],
    args: Sequence[Movable | float | int],
    snake_axes: Iterable | bool | None = None,
    md: CustomPlanMetadata | None = None,
) -> MsgGenerator:
    yield from prepare(analyser.sequence, sequence)
    yield from grid_scan(
        list(detectors) + [analyser],
        *args,
        snake_axes=snake_axes,
        per_step=analyser_nd_step,
        md=md,
    )
