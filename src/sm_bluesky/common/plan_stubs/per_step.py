from collections.abc import Mapping, Sequence
from typing import Any

from bluesky.plan_stubs import move_per_step, stage_all, trigger_and_read
from bluesky.protocols import (
    Movable,
    Readable,
)
from bluesky.utils import (
    MsgGenerator,
    plan,
)
from dodal.devices.electron_analyser import ElectronAnalyserRegionDetector
from dodal.devices.electron_analyser.abstract import (
    AbstractAnalyserDriverIO,
    AbstractBaseRegion,
)
from dodal.log import LOGGER


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

    analyser_detectors: list[
        ElectronAnalyserRegionDetector[AbstractAnalyserDriverIO, AbstractBaseRegion]
    ] = []
    other_detectors = []
    for det in detectors:
        if isinstance(det, ElectronAnalyserRegionDetector):
            analyser_detectors.append(det)
        else:
            other_detectors.append(det)

    yield from move_per_step(step, pos_cache)
    motors: list[Readable] = [s for s in step.keys() if isinstance(s, Readable)]

    # To get energy sources and open paired shutters, they need to be given in this
    # plan. They could possibly come from step but we then have to extract them out.
    # It would easier if they are part of the detector and the plan just calls the
    # common methods.
    for analyser_det in analyser_detectors:
        LOGGER.info(f"Scanning region {analyser_det.region.name}.")
        yield from stage_all(analyser_det)
        yield from trigger_and_read(
            [analyser_det] + list(other_detectors) + list(motors),
            name=analyser_det.region.name,
        )
