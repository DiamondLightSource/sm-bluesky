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
from ophyd_async.sim import SimMotor

from sm_bluesky.electron_analyser.plans.analyser_scans import (
    analysercount,
    analyserscan,
    grid_analyserscan,
    process_detectors_for_analyserscan,
)
from tests.electron_analyser.util import analyser_setup_for_scan


@pytest.fixture(params=[VGScientaDetector, SpecsDetector])
def detector_class(
    request: pytest.FixtureRequest,
) -> type[ElectronAnalyserDetector]:
    return request.param


@pytest.fixture(params=[0, 1, 2])
def extra_detectors(
    request: pytest.FixtureRequest,
) -> list[Readable]:
    return [SimMotor("det" + str(i + 1)) for i in range(request.param)]


@pytest.fixture
def all_detectors(
    sim_analyser: ElectronAnalyserDetector, extra_detectors: list[Readable]
) -> Sequence[Readable]:
    return [sim_analyser] + extra_detectors


async def test_process_detectors_for_analyserscan_func_correctly_replaces_detectors(
    sequence_file: str,
    sim_analyser: ElectronAnalyserDetector,
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


async def test_analysercount(
    RE: RunEngine,
    sim_analyser: ElectronAnalyserDetector,
    sequence_file: str,
    all_detectors: Sequence[Readable],
) -> None:
    analyser_setup_for_scan(sim_analyser)
    RE(analysercount(all_detectors, sequence_file))


@pytest.mark.parametrize(
    "args",
    [
        [SimMotor("motor1"), -10, 10],
        [SimMotor("motor1"), -10, 10, SimMotor("motor2"), -1, 1],
    ],
)
async def test_analyserscan(
    RE: RunEngine,
    sim_analyser: ElectronAnalyserDetector,
    sequence_file: str,
    all_detectors: Sequence[Readable],
    args: list[SimMotor | int],
) -> None:
    analyser_setup_for_scan(sim_analyser)
    RE(analyserscan(all_detectors, sequence_file, *args, num=10))


@pytest.mark.parametrize(
    "args",
    [
        [SimMotor("motor1"), 1, 10, 1],
        [SimMotor("motor1"), 1, 10, 1, SimMotor("motor2"), 1, 5, 1],
    ],
)
async def test_grid_analyserscan(
    RE: RunEngine,
    sim_analyser: ElectronAnalyserDetector,
    sequence_file: str,
    all_detectors: Sequence[Readable],
    args: list[SimMotor | int],
) -> None:
    analyser_setup_for_scan(sim_analyser)
    RE(grid_analyserscan(all_detectors, sequence_file, *args))
