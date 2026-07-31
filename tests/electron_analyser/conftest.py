import numpy as np
import pytest
from dodal.common.data_util import ModelLoader
from dodal.devices.beamlines import b07, b07_shared, i09
from dodal.devices.electron_analyser.base import (
    BaseSequence,
    ElectronAnalyserTriggerLogic,
    GenericElectronAnalyserDetector,
    RegionLogic,
)
from dodal.devices.electron_analyser.specs import SpecsAnalyserDriverIO, SpecsDetector
from dodal.devices.electron_analyser.vgscienta import (
    VGScientaAnalyserDriverIO,
    VGScientaDetector,
)
from dodal.devices.fast_shutter import DualFastShutter, FastShutter, GenericFastShutter
from dodal.devices.selectable_source import DualEnergySource, SelectedSource
from ophyd_async.core import (
    InOut,
    SignalR,
    SignalRW,
    init_devices,
    set_mock_value,
    soft_signal_rw,
)
from ophyd_async.epics.adcore import ADAcquireLogic

from tests.electron_analyser.util import (
    load_b07_specs_test_seq,
    load_i09_vgscienta_test_seq,
)


@pytest.fixture
def single_energy_source() -> SignalR[float]:
    with init_devices(mock=True):
        source1 = soft_signal_rw(float, initial_value=2200)

    return source1


@pytest.fixture
async def source_selector() -> SignalRW[SelectedSource]:
    async with init_devices(mock=True):
        source_selector = soft_signal_rw(SelectedSource)
    return source_selector


@pytest.fixture
def dual_energy_source(
    source_selector: SignalRW[SelectedSource], single_energy_source: SignalR[float]
) -> DualEnergySource:
    with init_devices(mock=True):
        source2 = soft_signal_rw(float, initial_value=500)
    with init_devices(mock=True):
        dual_energy_source = DualEnergySource(
            source1=single_energy_source,
            source2=source2,
            selected_source=source_selector,
        )
    return dual_energy_source


@pytest.fixture(params=["single_source", "dual_source"])
def energy_source(
    request: pytest.FixtureRequest,
    single_energy_source: SignalR[float],
    dual_energy_source: DualEnergySource,
) -> SignalR[float]:
    if request.param == "single":
        return single_energy_source
    return dual_energy_source.energy


@pytest.fixture
def shutter1() -> FastShutter[InOut]:
    with init_devices(mock=True):
        shutter1 = FastShutter[InOut](
            pv="TEST:",
            open_state=InOut.OUT,
            close_state=InOut.IN,
        )
    return shutter1


@pytest.fixture
def shutter2() -> FastShutter[InOut]:
    with init_devices(mock=True):
        shutter2 = FastShutter[InOut](
            pv="TEST:",
            open_state=InOut.OUT,
            close_state=InOut.IN,
        )
    return shutter2


@pytest.fixture
def dual_fast_shutter(
    shutter1: FastShutter[InOut],
    shutter2: FastShutter[InOut],
    source_selector: SignalRW[SelectedSource],
) -> DualFastShutter[InOut]:
    with init_devices(mock=True):
        dual_fast_shutter = DualFastShutter[InOut](
            shutter1,
            shutter2,
            source_selector,
        )
    return dual_fast_shutter


@pytest.fixture(params=["single_shutter", "dual_shutter"])
def shutter(
    request: pytest.FixtureRequest,
    shutter1: FastShutter[InOut],
    dual_fast_shutter: DualFastShutter[InOut],
) -> GenericFastShutter:
    if request.param == "single":
        return shutter1
    return dual_fast_shutter


@pytest.fixture
async def b07b_specs150(
    single_energy_source: SignalR[float],
) -> SpecsDetector[b07.LensMode, b07_shared.PsuMode]:
    with init_devices(mock=True):
        prefix = "TEST:"
        driver = SpecsAnalyserDriverIO(prefix, b07.LensMode, b07_shared.PsuMode)
        b07b_specs150 = SpecsDetector[b07.LensMode, b07_shared.PsuMode](
            prefix,
            driver,
            acquire_logic=ADAcquireLogic(driver),
            trigger_logic=ElectronAnalyserTriggerLogic(driver),
            region_logic=RegionLogic(driver, single_energy_source),
        )
    # Needed so we don't run into divide by zero errors on read and describe.
    dummy_val = 10
    set_mock_value(b07b_specs150.driver.slices, 1)
    set_mock_value(b07b_specs150.driver.min_angle_axis, dummy_val)
    set_mock_value(b07b_specs150.driver.max_angle_axis, dummy_val)
    set_mock_value(b07b_specs150.driver.slices, dummy_val)
    set_mock_value(b07b_specs150.driver.low_energy, dummy_val)
    set_mock_value(b07b_specs150.driver.high_energy, dummy_val)
    return b07b_specs150


@pytest.fixture
async def ew4000(
    dual_energy_source: DualEnergySource, source_selector: SignalRW[SelectedSource]
) -> VGScientaDetector[i09.LensMode, i09.PsuMode, i09.PassEnergy]:
    with init_devices(mock=True):
        prefix = "TEST:"
        driver = VGScientaAnalyserDriverIO(
            prefix, i09.LensMode, i09.PsuMode, i09.PassEnergy
        )
        ew4000 = VGScientaDetector[i09.LensMode, i09.PsuMode, i09.PassEnergy](
            prefix,
            driver,
            acquire_logic=ADAcquireLogic(driver),
            trigger_logic=ElectronAnalyserTriggerLogic(driver),
            region_logic=RegionLogic(
                driver, dual_energy_source.energy, source_selector
            ),
        )
    energy_axis = [1, 2, 3, 4, 5]
    set_mock_value(ew4000.driver.energy_axis, np.array(energy_axis, dtype=float))
    return ew4000


@pytest.fixture(params=["ew4000", "b07b_specs150"])
def sim_analyser(
    request: pytest.FixtureRequest,
    ew4000: VGScientaDetector[i09.LensMode, i09.PsuMode, i09.PassEnergy],
    b07b_specs150: SpecsDetector[b07.LensMode, b07_shared.PsuMode],
) -> GenericElectronAnalyserDetector:
    detectors = [ew4000, b07b_specs150]
    for detector in detectors:
        if detector.name == request.param:
            return detector
    raise ValueError(f"Detector with name '{request.param}' not found")


@pytest.fixture
def load_sequence(
    sim_analyser: GenericElectronAnalyserDetector,
) -> ModelLoader:
    if isinstance(sim_analyser, VGScientaDetector):
        return load_i09_vgscienta_test_seq
    elif isinstance(sim_analyser, SpecsDetector):
        return load_b07_specs_test_seq
    raise TypeError(f"Undefined sim_analyser type {type(sim_analyser)}")


@pytest.fixture
def sequence(load_sequence: ModelLoader[BaseSequence]) -> BaseSequence:
    return load_sequence()
