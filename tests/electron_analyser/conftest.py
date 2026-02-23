import pytest
from dodal.common.data_util import JsonModelLoader
from dodal.devices.beamlines import b07, b07_shared, i09
from dodal.devices.common_dcm import (
    DoubleCrystalMonochromatorWithDSpacing,
    PitchAndRollCrystal,
    StationaryCrystal,
)
from dodal.devices.electron_analyser.base import (
    DualEnergySource,
    EnergySource,
    GenericElectronAnalyserDetector,
)
from dodal.devices.electron_analyser.specs import SpecsDetector, SpecsSequence
from dodal.devices.electron_analyser.vgscienta import (
    VGScientaDetector,
    VGScientaSequence,
)
from dodal.devices.fast_shutter import DualFastShutter, GenericFastShutter
from dodal.devices.pgm import PlaneGratingMonochromator
from dodal.devices.selectable_source import SourceSelector
from ophyd_async.core import InOut, init_devices, set_mock_value

from tests.electron_analyser.test_data import (
    TEST_SPECS_SEQUENCE,
    TEST_VGSCIENTA_SEQUENCE,
)


@pytest.fixture
async def source_selector() -> SourceSelector:
    async with init_devices(mock=True):
        source_selector = SourceSelector()
    return source_selector


@pytest.fixture
async def single_energy_source() -> EnergySource:
    async with init_devices(mock=True):
        dcm = DoubleCrystalMonochromatorWithDSpacing(
            "DCM:", PitchAndRollCrystal, StationaryCrystal
        )
    await dcm.energy_in_keV.set(2.2)
    async with init_devices(mock=True):
        dcm_energy_source = EnergySource(dcm.energy_in_eV)

    return dcm_energy_source


@pytest.fixture
async def dual_energy_source(source_selector: SourceSelector) -> DualEnergySource:
    async with init_devices(mock=True):
        dcm = DoubleCrystalMonochromatorWithDSpacing(
            "DCM:", PitchAndRollCrystal, StationaryCrystal
        )
        pgm = PlaneGratingMonochromator("PGM:", i09.Grating)
    await dcm.energy_in_keV.set(2.2)
    await pgm.energy.set(500)
    async with init_devices(mock=True):
        dual_energy_source = DualEnergySource(
            source1=dcm.energy_in_eV,
            source2=pgm.energy.user_readback,
            selected_source=source_selector.selected_source,
        )
    return dual_energy_source


@pytest.fixture
def shutter1() -> GenericFastShutter[InOut]:
    with init_devices(mock=True):
        shutter1 = GenericFastShutter[InOut](
            pv="TEST:",
            open_state=InOut.OUT,
            close_state=InOut.IN,
        )
    return shutter1


@pytest.fixture
def shutter2() -> GenericFastShutter[InOut]:
    with init_devices(mock=True):
        shutter2 = GenericFastShutter[InOut](
            pv="TEST:",
            open_state=InOut.OUT,
            close_state=InOut.IN,
        )
    return shutter2


@pytest.fixture
def dual_fast_shutter(
    shutter1: GenericFastShutter[InOut],
    shutter2: GenericFastShutter[InOut],
    source_selector: SourceSelector,
) -> DualFastShutter[InOut]:
    with init_devices(mock=True):
        dual_fast_shutter = DualFastShutter[InOut](
            shutter1,
            shutter2,
            source_selector.selected_source,
        )
    return dual_fast_shutter


@pytest.fixture
async def b07b_specs150(
    single_energy_source: EnergySource,
    shutter1: GenericFastShutter,
) -> SpecsDetector[b07.LensMode, b07_shared.PsuMode]:
    with init_devices(mock=True):
        b07b_specs150 = SpecsDetector[b07.LensMode, b07_shared.PsuMode](
            prefix="TEST:",
            lens_mode_type=b07.LensMode,
            psu_mode_type=b07_shared.PsuMode,
            energy_source=single_energy_source,
            shutter=shutter1,
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
    dual_energy_source: DualEnergySource,
    dual_fast_shutter: DualFastShutter,
    source_selector: SourceSelector,
) -> VGScientaDetector[i09.LensMode, i09.PsuMode, i09.PassEnergy]:
    with init_devices(mock=True):
        ew4000 = VGScientaDetector[i09.LensMode, i09.PsuMode, i09.PassEnergy](
            prefix="TEST:",
            lens_mode_type=i09.LensMode,
            psu_mode_type=i09.PsuMode,
            pass_energy_type=i09.PassEnergy,
            energy_source=dual_energy_source,
            shutter=dual_fast_shutter,
            source_selector=source_selector,
        )
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


I09Sequence = VGScientaSequence[i09.LensMode, i09.PsuMode, i09.PassEnergy]
load_i09_vgscienta_test_seq = JsonModelLoader[I09Sequence](
    I09Sequence, TEST_VGSCIENTA_SEQUENCE
)
B07BSequence = SpecsSequence[b07.LensMode, b07_shared.PsuMode]
load_b07b_specs_test_seq = JsonModelLoader[B07BSequence](
    B07BSequence, TEST_SPECS_SEQUENCE
)


@pytest.fixture
def load_sequence(
    sim_analyser: GenericElectronAnalyserDetector,
) -> JsonModelLoader:
    if isinstance(sim_analyser, VGScientaDetector):
        return load_i09_vgscienta_test_seq
    elif isinstance(sim_analyser, SpecsDetector):
        return load_b07b_specs_test_seq
    raise TypeError(f"Undefined sim_analyser type {type(sim_analyser)}")
