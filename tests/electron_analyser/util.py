from typing import Any
from unittest.mock import ANY

from dodal.common.data_util import ModelLoader, ModelLoaderConfig, json_model_loader
from dodal.devices.beamlines import b07, b07_shared, i05_shared, i09
from dodal.devices.electron_analyser.base import (
    GenericAnalyserDriverIO,
    GenericRegion,
)
from dodal.devices.electron_analyser.mbs import MbsSequence
from dodal.devices.electron_analyser.specs import AcquisitionMode as SpecsAcqusitionMode
from dodal.devices.electron_analyser.specs import (
    SpecsAnalyserDriverIO,
    SpecsRegion,
    SpecsSequence,
)
from dodal.devices.electron_analyser.vgscienta import (
    VGScientaAnalyserDriverIO,
    VGScientaRegion,
    VGScientaSequence,
)

from tests.electron_analyser.test_data import (
    TEST_SPECS_SEQUENCE,
    TEST_VGSCIENTA_SEQUENCE,
)

B07SpecsSequence = SpecsSequence[b07.LensMode, b07_shared.PsuMode]
I09VGScientaSequence = VGScientaSequence[i09.LensMode, i09.PassEnergy]
I05MbsSequence = MbsSequence[i05_shared.LensMode, i05_shared.PassEnergy]


load_b07_specs_test_seq = ModelLoader[B07SpecsSequence](
    json_model_loader(B07SpecsSequence),
    ModelLoaderConfig.from_default_file(TEST_SPECS_SEQUENCE),
)
load_i09_vgscienta_test_seq = ModelLoader[I09VGScientaSequence](
    json_model_loader(I09VGScientaSequence),
    ModelLoaderConfig.from_default_file(TEST_VGSCIENTA_SEQUENCE),
)
# ToDo - Add Mbs


def expected_analyser_config(
    drv: GenericAnalyserDriverIO,
    epics_region: GenericRegion,
) -> dict[str, Any]:
    if isinstance(drv, VGScientaAnalyserDriverIO) and isinstance(
        epics_region, VGScientaRegion
    ):
        return expected_vgscienta_analyser_config(drv, epics_region)
    elif isinstance(drv, SpecsAnalyserDriverIO) and isinstance(
        epics_region, SpecsRegion
    ):
        return expected_specs_analyser_config(drv, epics_region)
    else:
        raise TypeError(
            f"Not a valid type for driver {type(drv)} and region {type(epics_region)} "
        )


def expected_vgscienta_analyser_config(
    drv: VGScientaAnalyserDriverIO,
    epics_region: VGScientaRegion,
) -> dict[str, Any]:
    return {
        drv.region_name.name: epics_region.name,
        drv.low_energy.name: epics_region.low_energy,
        drv.centre_energy.name: epics_region.centre_energy,
        drv.high_energy.name: epics_region.high_energy,
        drv.slices.name: epics_region.slices,
        drv.lens_mode.name: epics_region.lens_mode,
        drv.pass_energy.name: epics_region.pass_energy,
        drv.iterations.name: epics_region.iterations,
        drv.acquire_time.name: epics_region.acquire_time,
        drv.acquisition_mode.name: epics_region.acquisition_mode,
        drv.energy_step.name: epics_region.energy_step,
        drv.detector_mode.name: epics_region.detector_mode,
        drv.region_min_x.name: epics_region.min_x,
        drv.region_size_x.name: epics_region.size_x,
        drv.region_min_y.name: epics_region.min_y,
        drv.region_size_y.name: epics_region.size_y,
        drv.energy_mode.name: epics_region.energy_mode,
        drv.psu_mode.name: ANY,
    }


def expected_specs_analyser_config(
    drv: SpecsAnalyserDriverIO,
    epics_region: SpecsRegion,
) -> dict[str, Any]:
    if epics_region.acquisition_mode == SpecsAcqusitionMode.FIXED_TRANSMISSION:
        energy_step = epics_region.energy_step
    else:
        energy_step = ANY

    if epics_region.acquisition_mode == SpecsAcqusitionMode.FIXED_ENERGY:
        centre_energy = epics_region.centre_energy
    else:
        centre_energy = ANY

    return {
        drv.region_name.name: epics_region.name,
        drv.low_energy.name: epics_region.low_energy,
        drv.high_energy.name: epics_region.high_energy,
        drv.slices.name: epics_region.slices,
        drv.acquire_time.name: epics_region.acquire_time,
        drv.lens_mode.name: epics_region.lens_mode,
        drv.pass_energy.name: epics_region.pass_energy,
        drv.iterations.name: epics_region.iterations,
        drv.acquisition_mode.name: epics_region.acquisition_mode,
        drv.snapshot_values.name: epics_region.values,
        drv.psu_mode.name: epics_region.psu_mode,
        drv.energy_mode.name: epics_region.energy_mode,
        drv.slices.name: epics_region.slices,
        drv.energy_mode.name: epics_region.energy_mode,
        drv.psu_mode.name: epics_region.psu_mode,
        drv.snapshot_values.name: epics_region.values,
        drv.energy_step.name: energy_step,
        drv.centre_energy.name: centre_energy,
    }


def assert_mapped_data_equals_expected(
    data: dict[str, Any], expected: dict[str, Any], skip_expected_is_none: bool = True
) -> None:
    for key, exp in expected.items():
        assert key in data
        if skip_expected_is_none and exp is None:
            continue
        assert data[key] == exp
