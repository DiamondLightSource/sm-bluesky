import pytest
from bluesky import RunEngine
from dodal.devices.electron_analyser import ElectronAnalyserDetectorImpl
from dodal.devices.electron_analyser.specs import SpecsDetector
from dodal.devices.electron_analyser.vgscienta import VGScientaDetector
from ophyd_async.core import init_devices

from tests.electron_analyser.util import TEST_SPECS_SEQUENCE, TEST_VGSCIENTA_SEQUENCE


@pytest.fixture
async def sim_analyser(
    detector_class: type[ElectronAnalyserDetectorImpl], RE: RunEngine
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
