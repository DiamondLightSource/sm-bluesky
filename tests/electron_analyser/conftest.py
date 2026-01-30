import pytest
from dodal.beamlines import b07, i09
from dodal.devices.electron_analyser.base import (
    DualEnergySource,
    ElectronAnalyserDetector,
)
from dodal.devices.electron_analyser.specs import SpecsDetector
from dodal.devices.electron_analyser.vgscienta import VGScientaDetector
from dodal.devices.selectable_source import SourceSelector
from dodal.testing.electron_analyser import create_detector
from ophyd_async.core import init_devices
from ophyd_async.sim import SimMotor

from tests.electron_analyser.test_data import (
    TEST_SPECS_SEQUENCE,
    TEST_VGSCIENTA_SEQUENCE,
)
from tests.electron_analyser.util import analyser_setup_for_scan


@pytest.fixture
async def dcm_energy() -> SimMotor:
    with init_devices():
        dcm_energy = SimMotor()
    await dcm_energy.set(2200)
    return dcm_energy


@pytest.fixture
async def pgm_energy() -> SimMotor:
    with init_devices():
        pgm_energy = SimMotor()
    await pgm_energy.set(500)
    return pgm_energy


@pytest.fixture
async def source_selector() -> SourceSelector:
    with init_devices(mock=True):
        source_selector = SourceSelector()
    return source_selector


@pytest.fixture
async def dual_energy_source(
    dcm_energy: SimMotor, pgm_energy: SimMotor, source_selector: SourceSelector
) -> DualEnergySource:
    with init_devices():
        dual_energy_source = DualEnergySource(
            dcm_energy.user_readback,
            pgm_energy.user_readback,
            source_selector.selected_source,
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
    source_selector: SourceSelector,
    dual_energy_source: DualEnergySource,
) -> ElectronAnalyserDetector:
    with init_devices(mock=True):
        sim_analyser = create_detector(
            request.param,
            prefix="TEST:",
            energy_source=dual_energy_source,
            source_selector=source_selector,
        )
    analyser_setup_for_scan(sim_analyser)
    return sim_analyser


@pytest.fixture
def sequence_file(sim_analyser: ElectronAnalyserDetector) -> str:
    if isinstance(sim_analyser, VGScientaDetector):
        return TEST_VGSCIENTA_SEQUENCE
    elif isinstance(sim_analyser, SpecsDetector):
        return TEST_SPECS_SEQUENCE
    raise TypeError(f"Undefined sim_analyser type {type(sim_analyser)}")
