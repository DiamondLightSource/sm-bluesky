import pytest
from bluesky import RunEngine
from dodal.beamlines import b07, i09
from dodal.devices.electron_analyser import (
    ElectronAnalyserDetector,
    ElectronAnalyserDetectorImpl,
)
from dodal.devices.electron_analyser.specs import SpecsDetector
from dodal.devices.electron_analyser.vgscienta import VGScientaDetector
from dodal.testing.electron_analyser import create_detector
from ophyd_async.core import SignalR, init_devices
from ophyd_async.sim import SimMotor

from tests.electron_analyser.util import (
    TEST_SPECS_SEQUENCE,
    TEST_VGSCIENTA_SEQUENCE,
)


@pytest.fixture
async def pgm_energy(RE: RunEngine) -> SimMotor:
    return SimMotor("pgm_energy")


@pytest.fixture
async def dcm_energy(RE: RunEngine) -> SimMotor:
    return SimMotor("dcm_energy")


@pytest.fixture
async def energy_sources(
    dcm_energy: SimMotor, pgm_energy: SimMotor
) -> dict[str, SignalR[float]]:
    return {"source1": dcm_energy.user_readback, "source2": pgm_energy.user_readback}


@pytest.fixture(
    params=[
        VGScientaDetector[i09.LensMode, i09.PsuMode, i09.PassEnergy],
        SpecsDetector[b07.LensMode, b07.PsuMode],
    ]
)
async def sim_analyser(
    request: pytest.FixtureRequest,
    energy_sources: dict[str, SignalR[float]],
    RE: RunEngine,
) -> ElectronAnalyserDetector:
    with init_devices(mock=True):
        sim_analyser = await create_detector(
            request.param,
            prefix="TEST:",
            energy_sources=energy_sources,
        )
    return sim_analyser


@pytest.fixture
def sequence_file(sim_analyser: ElectronAnalyserDetectorImpl) -> str:
    if isinstance(sim_analyser, VGScientaDetector):
        return TEST_VGSCIENTA_SEQUENCE
    elif isinstance(sim_analyser, SpecsDetector):
        return TEST_SPECS_SEQUENCE
    raise TypeError(f"Undefined sim_analyser type {type(sim_analyser)}")
