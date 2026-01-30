from collections.abc import Iterable, Mapping, Sequence
from typing import Any, TypeVar

from bluesky.plan_stubs import move_per_step, mv, trigger_and_read
from bluesky.protocols import Movable, Readable
from bluesky.utils import (
    MsgGenerator,
    plan,
)
from dodal.devices.electron_analyser.base import ElectronAnalyserDetector
from dodal.log import LOGGER

T = TypeVar("T")


def get_first_of_type(objects: Iterable[Any], target_type: type[T]) -> T:
    for obj in objects:
        if isinstance(obj, target_type):
            return obj
    raise ValueError(f"Cannot find object from {objects} with type {target_type}")


@plan
def analyser_nd_step(
    detectors: Sequence[Readable],
    step: Mapping[Movable, Any],
    pos_cache: dict[Movable, Any],
    *args,
) -> MsgGenerator:
    """
    Inner loop of an N-dimensional step scan

    Modified default function for ``per_step`` param in ND plans. Performs an extra for
    loop for each ElectronAnalyserRegionDetector present so they can be collected one by
    one.

    Parameters
    ----------
    detectors : iterable
        devices to read
    step : dict
        mapping motors to positions in this step
    pos_cache : dict
        mapping motors to their last-set positions
    """

    # Step provides the map of motors to single position to move to. Move motors to
    # required positions.
    yield from move_per_step(step, pos_cache)

    # This is to satisfy type checking. Motors are Moveable and Readable, so make
    # them Readable so positions can be measured.
    motors: list[Readable] = [s for s in step.keys() if isinstance(s, Readable)]

    readables = list(detectors) + motors

    analyser = get_first_of_type(detectors, ElectronAnalyserDetector)

    sequence = analyser.sequence_loader.sequence
    if sequence is None:
        raise ValueError(f"{analyser.sequence_loader.name}.sequence is None.")

    for region in sequence.get_enabled_regions():
        LOGGER.info(f"Scanning region {region.name}.")
        yield from mv(analyser, region)
        yield from trigger_and_read(readables, name=region.name)


@plan
def analyser_shot(detectors: Sequence[Readable], *args) -> MsgGenerator:
    yield from analyser_nd_step(detectors, {}, {}, *args)
