import bluesky.plan_stubs as bps
from bluesky.utils import MsgGenerator, plan
from dodal.devices.electron_analyser import TElectronAnalyserDetectorImpl
from dodal.log import LOGGER


@plan
def analyserscan(
    analyser: TElectronAnalyserDetectorImpl,
    sequence_file: str,
) -> MsgGenerator:
    # ToDo - Add motor arguments to loop through and measure at

    detectors = analyser.create_region_detector_list(sequence_file)
    LOGGER.info("Found regions: " + str([det.region.name for det in detectors]))

    yield from bps.open_run()

    for det in detectors:
        yield from bps.stage_all(analyser)
        region_name = det.region.name
        LOGGER.info(f"Acquiring region {region_name}")
        yield from bps.trigger_and_read([det], name=region_name)
        LOGGER.info("Finished acquiring region.")
        yield from bps.unstage_all(analyser)

    LOGGER.info("Closing run")
    yield from bps.close_run()
