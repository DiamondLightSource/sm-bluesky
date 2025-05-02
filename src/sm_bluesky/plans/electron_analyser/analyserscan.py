from collections.abc import Callable, Coroutine
from typing import Any

import bluesky.plan_stubs as bps
from bluesky.utils import MsgGenerator, plan
from dodal.devices.electron_analyser import (
    ElectronAnalyserDetector,
    SpecsAnalyserDriverIO,
    VGScientaAnalyserDriverIO,
)
from dodal.devices.electron_analyser.abstract_analyser_io import (
    AbstractAnalyserDriverIO,
)
from dodal.devices.electron_analyser.abstract_region import (
    AbstractBaseRegion,
    AbstractBaseSequence,
)
from dodal.log import LOGGER
from dodal.plan_stubs.electron_analyser.configure_driver import (
    configure_specs,
    configure_vgscienta,
)

ANALYSER_TYPE_LOOKUP: dict[type[AbstractAnalyserDriverIO], Callable] = {
    VGScientaAnalyserDriverIO: configure_vgscienta,
    SpecsAnalyserDriverIO: configure_specs,
}


# ToDo - configure plan needs to be moved to device stage / unstage method?
def get_configure_plan_for_analyser(
    analyser: AbstractAnalyserDriverIO,
) -> Callable[..., Coroutine[Any, Any, Any]]:
    configure_plan = ANALYSER_TYPE_LOOKUP.get(type(analyser))

    if configure_plan is None:
        raise ValueError(f"No configure plan found for analyser type: {type(analyser)}")
    return configure_plan


@plan
def analyserscan(
    analyser: ElectronAnalyserDetector[AbstractBaseSequence, AbstractBaseRegion],
    sequence_file: str,
) -> MsgGenerator:
    # ToDo - Add motor arguments to loop through and measure at

    detectors = analyser.create_region_detectors(sequence_file)
    LOGGER.info("Found regions: " + str([det.region.name for det in detectors]))

    yield from bps.open_run()
    yield from bps.stage_all(analyser)

    for det in detectors:
        # ToDo - Add live excitation energy and shutter movement. Inside plan or device?
        # Use place holder for now
        exctiation_energy = 1000
        # yield from bps.prepare(det) #Maybe need to make detector preparable with the excitation_energy?
        region_name = det.region.name
        LOGGER.info(f"Acquiring region {region_name}")
        yield from bps.trigger_and_read([det], name=region_name)
        LOGGER.info("Finished acquiring region.")

    yield from bps.unstage_all(analyser)

    LOGGER.info("Closing run")
    yield from bps.close_run()
