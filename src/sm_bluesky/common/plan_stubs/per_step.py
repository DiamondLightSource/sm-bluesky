from collections.abc import Mapping, Sequence
from typing import Any, Optional

from bluesky.plan_stubs import TakeReading, abs_set, checkpoint, trigger_and_read, wait
from bluesky.protocols import (
    Movable,
    Readable,
)
from bluesky.utils import (
    MsgGenerator,
    plan,
    short_uid,
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
    take_reading: Optional[TakeReading] = None,
) -> MsgGenerator[None]:
    """
    Inner loop of an N-dimensional step scan

    This is the default function for ``per_step`` param in ND plans.

    Parameters
    ----------
    detectors : iterable
        devices to read
    step : dict
        mapping motors to positions in this step
    pos_cache : dict
        mapping motors to their last-set positions
    """

    def move():
        yield from checkpoint()
        grp = short_uid("set")
        for motor, pos in step.items():
            if pos == pos_cache[motor]:
                # This step does not move this motor.
                continue
            yield from abs_set(motor, pos, group=grp)
            pos_cache[motor] = pos
        yield from wait(group=grp)

    analyser_detectors: list[
        ElectronAnalyserRegionDetector[AbstractAnalyserDriverIO, AbstractBaseRegion]
    ] = []
    other_detectors = []
    for det in detectors:
        if isinstance(det, ElectronAnalyserRegionDetector):
            analyser_detectors.append(det)
        else:
            other_detectors.append(det)

    motors: list[Readable] = [s for s in step.keys() if isinstance(s, Readable)]
    yield from move()

    # To get energy sources and open paired shutters, they need to be given in this
    # plan. They could possibly come from step but we then have to extract them out.
    # It would easier if they are part of the detector and the plan just calls the
    # common methods.
    for analyser_det in analyser_detectors:
        LOGGER.info(f"Scanning region {analyser_det.region.name}.")
        yield from trigger_and_read(
            [analyser_det] + list(other_detectors) + list(motors),
            name=analyser_det.region.name,
        )
