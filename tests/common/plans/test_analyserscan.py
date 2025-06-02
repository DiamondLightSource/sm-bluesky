import os
from collections.abc import Sequence

import pytest
from bluesky.protocols import Readable
from bluesky.run_engine import RunEngine
from dodal.devices.electron_analyser import (
    ElectronAnalyserDetector,
    ElectronAnalyserRegionDetector,
)
from dodal.devices.electron_analyser.abstract import (
    AbstractAnalyserDriverIO,
    AbstractBaseRegion,
)
from dodal.devices.electron_analyser.specs import SpecsDetector
from dodal.devices.electron_analyser.vgscienta import VGScientaDetector
from ophyd_async.core import init_devices
from ophyd_async.epics.motor import Motor

from sm_bluesky.common.plans.analyserscan import process_detectors_for_analyserscan

ElectronAnalyserDetectorImpl = VGScientaDetector | SpecsDetector

TEST_DATA_PATH = "tests/test_data/electron_analyser/"

TEST_VGSCIENTA_SEQUENCE = os.path.join(TEST_DATA_PATH, "vgscienta_sequence.seq")
TEST_SPECS_SEQUENCE = os.path.join(TEST_DATA_PATH, "specs_sequence.seq")


@pytest.fixture(params=[VGScientaDetector, SpecsDetector])
def detector_class(
    request: pytest.FixtureRequest,
) -> type[ElectronAnalyserDetector]:
    return request.param


@pytest.fixture
async def sim_analyser(
    detector_class: type[ElectronAnalyserDetectorImpl],
) -> ElectronAnalyserDetectorImpl:
    async with init_devices(mock=True, connect=True):
        sim_detector = detector_class(
            prefix="TEST:",
        )
    return sim_detector


@pytest.fixture
def sequence_file(sim_analyser: ElectronAnalyserDetectorImpl) -> str:
    if isinstance(sim_analyser, VGScientaDetector):
        return TEST_VGSCIENTA_SEQUENCE
    elif isinstance(sim_analyser, SpecsDetector):
        return TEST_SPECS_SEQUENCE
    raise TypeError(f"Undefined sim_analyser type {type(sim_analyser)}")


@pytest.fixture(params=[0, 1, 2])
async def extra_detectors(
    request: pytest.FixtureRequest,
) -> list[Readable]:
    async def detector() -> Motor:
        async with init_devices(mock=True, connect=True):
            sim_driver = Motor(
                prefix="TEST:",
            )
        return sim_driver

    return [await detector() for i in range(request.param)]


@pytest.fixture
def all_detectors(
    sim_analyser: ElectronAnalyserDetectorImpl, extra_detectors: list[Readable]
) -> Sequence[Readable]:
    return [sim_analyser] + extra_detectors


async def test_process_detectors_for_analyserscan_func_correctly_replaces_detectors(
    sequence_file: str,
    sim_analyser: ElectronAnalyserDetectorImpl,
    extra_detectors: Sequence[Readable],
    all_detectors: Sequence[Readable],
):
    sequence = sim_analyser.load_sequence(sequence_file)

    analyserscan_detectors: Sequence[Readable] = process_detectors_for_analyserscan(
        all_detectors, sequence_file
    )
    # Check analyser detector is removed from detector list
    assert sim_analyser not in analyserscan_detectors
    # Check all extra detectors are still present in detector list
    for extra_det in extra_detectors:
        assert extra_det in analyserscan_detectors

    region_detectors: list[
        ElectronAnalyserRegionDetector[AbstractAnalyserDriverIO, AbstractBaseRegion]
    ] = [
        ad
        for ad in analyserscan_detectors
        if isinstance(ad, ElectronAnalyserRegionDetector)
    ]

    # Check length of region_detectors list is length of sequence enabled regions
    assert len(region_detectors) == len(sequence.get_enabled_region_names())

    # ToDo - We cannot compare that the region detectors are the same without override
    # equals method. For now, just compare that region name is the same.
    for region_det in region_detectors:
        assert region_det.region.name in sequence.get_enabled_region_names()
