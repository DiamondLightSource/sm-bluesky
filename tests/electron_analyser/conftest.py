import pytest
from bluesky import RunEngine
from dodal.beamlines import b07, i09
from dodal.devices.electron_analyser import DualEnergySource, ElectronAnalyserDetector
from dodal.devices.electron_analyser.specs import SpecsDetector
from dodal.devices.electron_analyser.vgscienta import VGScientaDetector
from dodal.testing.electron_analyser import create_detector
from ophyd_async.core import init_devices
from ophyd_async.sim import SimMotor

from tests.electron_analyser.test_data import (
    TEST_SPECS_SEQUENCE,
    TEST_VGSCIENTA_SEQUENCE,
)


@pytest.fixture
async def pgm_energy(RE: RunEngine) -> SimMotor:
    with init_devices():
        pgm_energy = SimMotor()
    return pgm_energy


@pytest.fixture
async def dcm_energy(RE: RunEngine) -> SimMotor:
    with init_devices():
        dcm_energy = SimMotor()
    return dcm_energy


@pytest.fixture
async def dual_energy_source(
    dcm_energy: SimMotor, pgm_energy: SimMotor, RE: RunEngine
) -> DualEnergySource:
    with init_devices():
        dual_energy_source = DualEnergySource(
            dcm_energy.user_readback, pgm_energy.user_readback
        )
    return dual_energy_source


@pytest.fixture(
    params=[
        VGScientaDetector[i09.LensMode, i09.PsuMode, i09.PassEnergy],
        SpecsDetector[b07.LensMode, b07.PsuMode],
    ]
)
async def sim_analyser(
    request: pytest.FixtureRequest,
    dual_energy_source: DualEnergySource,
    RE: RunEngine,
) -> ElectronAnalyserDetector:
    with init_devices(mock=True):
        sim_analyser = await create_detector(
            request.param,
            prefix="TEST:",
            energy_source=dual_energy_source,
        )
    return sim_analyser


@pytest.fixture
def sequence_file(sim_analyser: ElectronAnalyserDetector) -> str:
    if isinstance(sim_analyser, VGScientaDetector):
        return TEST_VGSCIENTA_SEQUENCE
    elif isinstance(sim_analyser, SpecsDetector):
        return TEST_SPECS_SEQUENCE
    raise TypeError(f"Undefined sim_analyser type {type(sim_analyser)}")
