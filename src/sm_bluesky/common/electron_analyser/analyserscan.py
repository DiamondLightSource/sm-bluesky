import bluesky.plan_stubs as bps
from bluesky.utils import MsgGenerator, plan
from dodal.common.coordination import inject
from dodal.devices.electron_analyser import ElectronAnalyserDetector
from dodal.devices.electron_analyser.abstract import (
    AbstractAnalyserDriverIO,
    AbstractBaseRegion,
    AbstractBaseSequence,
)
from dodal.log import LOGGER
from ophyd_async.core import DeviceVector
from ophyd_async.epics.motor import Motor

from sm_bluesky.common.electron_analyser.energy_source import (
    get_energy_source_for_region,
)


@plan
def analyserscan(
    analyser: ElectronAnalyserDetector[
        AbstractAnalyserDriverIO, AbstractBaseSequence, AbstractBaseRegion
    ],
    sequence_file: str,
    energy_sources: DeviceVector[Motor] = inject("energy_source"),
) -> MsgGenerator:
    # ToDo - Add motor arguments to loop through and measure at

    detectors = analyser.create_region_detector_list(sequence_file)
    LOGGER.info("Found regions: " + str([det.region.name for det in detectors]))

    yield from bps.open_run()

    for det in detectors:
        excitation_energy_source: Motor = get_energy_source_for_region(
            det.region, energy_sources
        )

        # Pass excitation energy source to the detector so binding energy can be
        # converted back to kinetic
        yield from bps.prepare(det, excitation_energy_source)
        yield from bps.stage_all(det)

        # ToDo - open / close shutter based on excitation energy source here.

        region_name = det.region.name
        LOGGER.info(f"Acquiring region {region_name}")
        yield from bps.trigger_and_read([det], name=region_name)
        LOGGER.info("Finished acquiring region.")
        yield from bps.unstage_all(analyser)

    LOGGER.info("Closing run")
    yield from bps.close_run()
