from typing import Any
from unittest.mock import ANY

from dodal.devices.electron_analyser.base import (
    ElectronAnalyserDetector,
    GenericAnalyserDriverIO,
    GenericRegion,
)
from dodal.devices.electron_analyser.specs import AcquisitionMode as SpecsAcqusitionMode
from dodal.devices.electron_analyser.specs import (
    SpecsAnalyserDriverIO,
    SpecsDetector,
    SpecsRegion,
)
from dodal.devices.electron_analyser.vgscienta import (
    VGScientaAnalyserDriverIO,
    VGScientaRegion,
)
from ophyd_async.core import set_mock_value


def analyser_setup_for_scan(sim_analyser: ElectronAnalyserDetector):
    if isinstance(sim_analyser, SpecsDetector):
        # Needed so we don't run into divide by zero errors on read and describe.
        dummy_val = 10
        set_mock_value(sim_analyser.driver.min_angle_axis, dummy_val)
        set_mock_value(sim_analyser.driver.max_angle_axis, dummy_val)
        set_mock_value(sim_analyser.driver.slices, dummy_val)
        set_mock_value(sim_analyser.driver.low_energy, dummy_val)
        set_mock_value(sim_analyser.driver.high_energy, dummy_val)


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
