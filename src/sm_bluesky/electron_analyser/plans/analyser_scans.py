from collections.abc import Iterable, Sequence
from typing import Annotated, Any, TypeVar

from bluesky import plan_stubs as bps
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

from sm_bluesky.electron_analyser.plan_stubs import (
    analyser_nd_step,
    analyser_shot,
)


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
    sequence: AbstractBaseSequence,
    detectors: Sequence[Readable],
    *args: Movable | Any,
    num: int | None = None,
    md: CustomPlanMetadata | None = None,
) -> MsgGenerator:
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
    *args: Any,
    snake_axes: Iterable | bool | None = None,
    md: CustomPlanMetadata | None = None,
) -> MsgGenerator:
    reg_detectors = analyser.create_region_detector_list(sequence.get_enabled_regions())
    yield from grid_scan(
        reg_detectors + list(detectors),
        *args,
        snake_axes=snake_axes,
        per_step=analyser_nd_step,
        md=md,
    )


T = TypeVar("T")

Group = Annotated[str, "String identifier used by 'wait' or stubs that await"]


def set_relative2(
    movable: Movable[T], value: T, group: Group | None = None, wait: bool = False
) -> MsgGenerator:
    """Change a device, wrapper for `bp.rel_set`.

    Args:
        movable (Movable): The device to set.
        value (T): The new value.
        group (Group | None, optional): The message group to associate with the setting,
            for sequencing. Defaults to None.
        wait (bool, optional): The group should wait until all setting is complete (e.g.
            a motor has finished moving). Defaults to False.

    Returns:
        MsgGenerator: Plan.

    Yields:
        Iterator[MsgGenerator]: Bluesky messages.
    """
    return (yield from bps.rel_set(movable, value, group=group, wait=wait))


@plan
def test_move(
    *args: Movable[Any] | Any, group: str | None = None, wait: bool = True
) -> MsgGenerator:
    yield from bps.abs_set(args[0], args[1], group=group, wait=wait)
