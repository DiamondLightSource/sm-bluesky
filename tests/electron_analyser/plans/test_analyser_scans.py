from collections.abc import Sequence

import pytest
from bluesky import RunEngine
from bluesky.protocols import Readable
from dodal.common.data_util import JsonModelLoader
from dodal.devices.electron_analyser.base import (
    AbstractBaseSequence,
    ElectronAnalyserDetector,
)
from ophyd_async.sim import SimMotor

from sm_bluesky.electron_analyser.plans.analyser_scans import (
    analysercount,
    analyserscan,
    grid_analyserscan,
)


@pytest.fixture(params=[0, 1, 2])
def extra_detectors(
    request: pytest.FixtureRequest,
) -> list[Readable]:
    return [SimMotor("det" + str(i + 1)) for i in range(request.param)]


async def test_analysercount(
    run_engine: RunEngine,
    sim_analyser: ElectronAnalyserDetector,
    load_sequence: JsonModelLoader[AbstractBaseSequence],
    extra_detectors: Sequence[Readable],
) -> None:
    run_engine(analysercount(sim_analyser, load_sequence(), extra_detectors))


@pytest.mark.parametrize(
    "args",
    [
        [SimMotor("motor1"), -10, 10],
        [SimMotor("motor1"), -10, 10, SimMotor("motor2"), -1, 1],
    ],
)
async def test_analyserscan(
    run_engine: RunEngine,
    sim_analyser: ElectronAnalyserDetector,
    load_sequence: JsonModelLoader[AbstractBaseSequence],
    extra_detectors: Sequence[Readable],
    args: list[SimMotor | int],
) -> None:
    run_engine(
        analyserscan(sim_analyser, load_sequence(), extra_detectors, *args, num=10)
    )


@pytest.mark.parametrize(
    "args",
    [
        [SimMotor("motor1"), 1, 10, 1],
        [SimMotor("motor1"), 1, 10, 1, SimMotor("motor2"), 1, 5, 1],
    ],
)
async def test_grid_analyserscan(
    run_engine: RunEngine,
    sim_analyser: ElectronAnalyserDetector,
    load_sequence: JsonModelLoader[AbstractBaseSequence],
    extra_detectors: Sequence[Readable],
    args: list[SimMotor | int],
) -> None:
    run_engine(grid_analyserscan(sim_analyser, load_sequence(), extra_detectors, *args))
