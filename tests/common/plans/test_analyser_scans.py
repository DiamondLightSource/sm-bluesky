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
from ophyd_async.testing import set_mock_value

from sm_bluesky.common.plans.analyser_scans import (
    analysercount,
    analyserscan,
    grid_analyserscan,
    process_detectors_for_analyserscan,
)

ElectronAnalyserDetectorImpl = VGScientaDetector | SpecsDetector

TEST_DATA_PATH = "tests/test_data/electron_analyser/"

TEST_VGSCIENTA_SEQUENCE = os.path.join(TEST_DATA_PATH, "vgscienta_sequence.seq")
TEST_SPECS_SEQUENCE = os.path.join(TEST_DATA_PATH, "specs_sequence.seq")


async def create_motor(name: str) -> Motor:
    async with init_devices(mock=True, connect=True):
        sim_motor = Motor(prefix="TEST:", name=name)
    # Needed so we don't get divide by zero errors when used in a scan.
    set_mock_value(sim_motor.velocity, 1)
    return sim_motor


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
    return [await create_motor("det" + str(i + 1)) for i in range(request.param)]


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


def analyser_setup_for_scan(sim_analyser: ElectronAnalyserDetectorImpl):
    if isinstance(sim_analyser, SpecsDetector):
        # Needed so we don't run into divide by zero errors on read and describe.
        dummy_val = 10
        set_mock_value(sim_analyser.driver.min_angle_axis, dummy_val)
        set_mock_value(sim_analyser.driver.max_angle_axis, dummy_val)
        set_mock_value(sim_analyser.driver.slices, dummy_val)
        set_mock_value(sim_analyser.driver.low_energy, dummy_val)
        set_mock_value(sim_analyser.driver.high_energy, dummy_val)


@pytest.fixture
async def args(
    request: pytest.FixtureRequest,
) -> list[Motor | int]:
    args = request.param
    # Need to wrap here rather than directly creating the motor so it can support async.
    return [
        await create_motor("motor" + str(i)) if a == Motor else a
        for i, a in enumerate(args)
    ]


async def test_analysercount(
    RE: RunEngine,
    sim_analyser: ElectronAnalyserDetectorImpl,
    sequence_file: str,
    all_detectors: Sequence[Readable],
) -> None:
    analyser_setup_for_scan(sim_analyser)
    RE(analysercount(all_detectors, sequence_file))


@pytest.mark.parametrize(
    "args",
    [
        [Motor, -10, 10],
        [Motor, -10, 10, Motor, -1, 1],
    ],
    indirect=True,
)
async def test_analyserscan(
    RE: RunEngine,
    sim_analyser: ElectronAnalyserDetectorImpl,
    sequence_file: str,
    all_detectors: Sequence[Readable],
    args: list[Motor | int],
) -> None:
    analyser_setup_for_scan(sim_analyser)
    RE(analyserscan(all_detectors, sequence_file, *args, num=10))


@pytest.mark.parametrize(
    "args",
    [
        [Motor, 1, 10, 1],
        [Motor, 1, 10, 1, Motor, 1, 5, 1],
    ],
    indirect=True,
)
async def test_grid_analyserscan(
    RE: RunEngine,
    sim_analyser: ElectronAnalyserDetectorImpl,
    sequence_file: str,
    all_detectors: Sequence[Readable],
    args: list[Motor | int],
) -> None:
    analyser_setup_for_scan(sim_analyser)
    RE(grid_analyserscan(all_detectors, sequence_file, *args))
