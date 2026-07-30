from collections.abc import Mapping, Sequence
from typing import Any, TypeVar

from bluesky.plan_stubs import TakeReading, move_per_step, mv, trigger_and_read
from bluesky.plans import PerShot, PerStepND
from bluesky.protocols import Movable, Readable
from bluesky.utils import MsgGenerator, plan
from dodal.devices.electron_analyser.base import BaseSequence, ElectronAnalyserDetector
from dodal.devices.fast_shutter import GenericFastShutter
from dodal.log import LOGGER

T = TypeVar("T")


@plan
def _analyser_regions(
    analyser: ElectronAnalyserDetector,
    sequence: BaseSequence,
    readables: Sequence[Readable],
    shutter: GenericFastShutter | None,
    close_shutter_per_region: bool,
) -> MsgGenerator:
    """
    Configure and collect data from each enabled electron analyser region.

    For each region, the analyser is configured, the optional shutter is opened,
    and the provided readables are triggered and read. The shutter is optionally
    closed after each region.

    Parameters
    ----------
    analyser:
        Electron analyser to configure for each region.
    sequence:
        Sequence containing the analyser regions to collect.
    readables:
        Devices to trigger and read for each region.
    shutter:
        Optional shutter to open before collecting each region.
    closer_shutter_per_region:
        Whether to close the shutter after collecting each region.
    """

    for region in sequence.get_enabled_regions():
        LOGGER.info(f"Scanning region {region.name}.")
        yield from mv(analyser, region)

        if shutter is not None:
            yield from mv(shutter.open, True)

        yield from trigger_and_read(readables, name=region.name)

        if close_shutter_per_region and shutter is not None:
            yield from mv(shutter.open, False)


def make_analyser_per_shot(
    analyser: ElectronAnalyserDetector,
    sequence: BaseSequence,
    close_shutter_per_region: bool,
    shutter: GenericFastShutter | None,
) -> PerShot:
    """
    Create a custom per-shot callback for acquisitions involving an electron analyser.

    The callback iterates over each enabled analyser region, configuring the analyser
    and optionally opening and closing a shutter for each region before triggering
    and reading the detectors.

    Parameters
    ----------
    analyser:
        Electron analyser to configure for each region and measure with.
    sequence:
        Sequence containing the analyser regions to collect.
    closer_shutter_per_region:
        Whether to close the shutter after collecting each region.
    shutter:
        Optional shutter to open before collecting each region.
    """
    if close_shutter_per_region and shutter is None:
        raise ValueError(
            "closer_shutter_per_region=True requires a shutter to be provided."
        )

    @plan
    def analyser_shot(
        detectors: Sequence[Readable], take_reading: TakeReading | None = None
    ) -> MsgGenerator:
        yield from _analyser_regions(
            analyser,
            sequence,
            detectors,
            shutter,
            close_shutter_per_region,
        )

    return analyser_shot


def make_analyser_per_step(
    analyser: ElectronAnalyserDetector,
    sequence: BaseSequence,
    close_shutter_per_region: bool,
    shutter: GenericFastShutter | None,
) -> PerStepND:
    """
    Create a custom per-step callback for scans involving an electron analyser.

    The callback moves the scan motors, then iterates over each enabled analyser
    region, configuring the analyser and optionally opening and closing a shutter
    for each region before triggering and reading the detectors and scan motors.

    Parameters
    ----------
    analyser:
        Electron analyser to configure for each region and measure with.
    sequence:
        Sequence containing the analyser regions to collect.
    close_shutter_per_region:
        Whether to close the shutter after collecting each region.
    shutter:
        Optional shutter to open before collecting each region.
    """
    if close_shutter_per_region and shutter is None:
        raise ValueError(
            "closer_shutter_per_region=True requires a shutter to be provided."
        )

    @plan
    def analyser_nd_step(
        detectors: Sequence[Readable],
        step: Mapping[Movable, Any],
        pos_cache: dict[Movable, Any],
        take_reading: TakeReading | None = None,
    ) -> MsgGenerator:
        yield from move_per_step(step, pos_cache)

        # Get any readables from the movables
        readables: list[Readable] = [s for s in step.keys() if isinstance(s, Readable)]
        yield from _analyser_regions(
            analyser,
            sequence,
            [*detectors, *readables],
            shutter,
            close_shutter_per_region,
        )

    return analyser_nd_step
