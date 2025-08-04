from typing import get_args, get_origin

import pytest
from bluesky import RunEngine
from dodal.devices.electron_analyser import ElectronAnalyserDetectorImpl
from dodal.devices.electron_analyser.specs import SpecsDetector
from dodal.devices.electron_analyser.vgscienta import VGScientaDetector
from ophyd_async.core import SignalR, init_devices
from ophyd_async.sim import SimMotor

from tests.electron_analyser.util import TEST_SPECS_SEQUENCE, TEST_VGSCIENTA_SEQUENCE


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


@pytest.fixture
async def sim_analyser(
    detector_class: type[ElectronAnalyserDetectorImpl],
    energy_sources: dict[str, SignalR[float]],
    RE: RunEngine,
) -> ElectronAnalyserDetectorImpl:
    # ToDo - this needs to use what dodal uses once this is implemented
    # https://github.com/DiamondLightSource/dodal/issues/1396
    parameters = {
        "prefix": "TEST:",
        "lens_mode_type": get_args(detector_class)[0],
        "psu_mode_type": get_args(detector_class)[1],
        "energy_sources": energy_sources,
    }
    if get_origin(detector_class) is VGScientaDetector:
        parameters["pass_energy_type"] = get_args(detector_class)[2]

    async with init_devices(mock=True, connect=True):
        sim_detector = detector_class(**parameters)
    return sim_detector


@pytest.fixture
def sequence_file(sim_analyser: ElectronAnalyserDetectorImpl) -> str:
    if isinstance(sim_analyser, VGScientaDetector):
        return TEST_VGSCIENTA_SEQUENCE
    elif isinstance(sim_analyser, SpecsDetector):
        return TEST_SPECS_SEQUENCE
    raise TypeError(f"Undefined sim_analyser type {type(sim_analyser)}")
