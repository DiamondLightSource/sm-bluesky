from collections.abc import Mapping, Sequence
from typing import Any

from bluesky.plan_stubs import (
    abs_set,
    move_per_step,
    trigger_and_read,
)
from bluesky.protocols import Movable, Readable
from bluesky.utils import (
    MsgGenerator,
    plan,
)
from dodal.devices.electron_analyser import (
    ElectronAnalyserRegionDetector,
    GenericElectronAnalyserRegionDetector,
)
from dodal.log import LOGGER


@plan
def analyser_shot(detectors: Sequence[Readable], *args) -> MsgGenerator:
    yield from analyser_nd_step(detectors, {}, {}, *args)


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

    analyser_detectors: list[GenericElectronAnalyserRegionDetector] = []
    other_detectors = []
    for det in detectors:
        if isinstance(det, ElectronAnalyserRegionDetector):
            analyser_detectors.append(det)
        else:
            other_detectors.append(det)

    # Step provides the map of motors to single position to move to. Move motors to
    # required positions.
    yield from move_per_step(step, pos_cache)

    # This is to satisfy type checking. Motors are Moveable and Readable, so make
    # them Readable so positions can be measured.
    motors: list[Readable] = [s for s in step.keys() if isinstance(s, Readable)]

    # To get energy sources and open paired shutters, they need to be given in this
    # plan. They could possibly come from step but we then have to extract them out.
    # It would also mean forcefully adding in the devices at the wrapper level.
    # It would easier if they are part of the detector and the plan just calls the
    # common methods so it is more dynamic and configuration only for device.
    for analyser_det in analyser_detectors:
        dets = [analyser_det] + list(other_detectors) + list(motors)

        # This is a work around until we can find a way to get the energy sources to use
        # the prepare method.
        yield from abs_set(analyser_det.driver, analyser_det.region)
        LOGGER.info(f"Scanning region {analyser_det.region.name}.")
        yield from trigger_and_read(
            dets,
            name=analyser_det.region.name,
        )
