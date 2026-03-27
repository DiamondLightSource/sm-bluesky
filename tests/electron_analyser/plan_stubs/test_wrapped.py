from unittest.mock import ANY

import pytest
from bluesky import RunEngine
from dodal.common.data_util import JsonModelLoader
from dodal.devices.electron_analyser.base import (
    AbstractBaseRegion,
    AbstractBaseSequence,
    ElectronAnalyserDetector,
    to_kinetic_energy,
)
from dodal.devices.electron_analyser.specs import SpecsDetector, SpecsRegion
from dodal.devices.electron_analyser.vgscienta import VGScientaDetector, VGScientaRegion
from ophyd_async.testing import assert_configuration, partial_reading

from sm_bluesky.electron_analyser.plan_stubs import set_region
from sm_bluesky.electron_analyser.plan_stubs.wrapped import dict_to_sequence


@pytest.fixture
def seq(
    sim_analyser: ElectronAnalyserDetector,
    load_sequence: JsonModelLoader[AbstractBaseSequence[AbstractBaseRegion]],
) -> AbstractBaseSequence[AbstractBaseRegion]:
    # Convert sequence to dictionary and back to model just to verify serialisation with
    # blueapi works and tests below verify it was converted correctly.
    return dict_to_sequence(sim_analyser, load_sequence().model_dump())


async def test_set_region_with_dict(
    run_engine: RunEngine,
    sim_analyser: ElectronAnalyserDetector,
    seq: AbstractBaseSequence[AbstractBaseRegion],
) -> None:
    for region in seq.regions:
        region_dict = region.model_dump()
        run_engine(set_region(sim_analyser, region_dict))
        await assert_analyser_configuration(sim_analyser, region)


async def test_set_region_with_region_model(
    run_engine: RunEngine,
    sim_analyser: ElectronAnalyserDetector,
    seq: AbstractBaseSequence[AbstractBaseRegion],
) -> None:
    for region in seq.regions:
        run_engine(set_region(sim_analyser, region))
        await assert_analyser_configuration(sim_analyser, region)


async def assert_analyser_configuration(
    analyser: ElectronAnalyserDetector, region: AbstractBaseRegion
) -> None:
    if isinstance(analyser, VGScientaDetector) and isinstance(region, VGScientaRegion):
        await assert_analyser_vgscienta_configuration(analyser, region)
    elif isinstance(analyser, SpecsDetector) and isinstance(region, SpecsRegion):
        await assert_analyser_specs_configuration(analyser, region)


async def assert_analyser_specs_configuration(
    sim_analyser: SpecsDetector, region: SpecsRegion
) -> None:
    sim_driver = sim_analyser._controller.driver
    energy = await sim_analyser._controller.energy_source.energy.get_value()
    prefix = sim_driver.name + "-"
    await assert_configuration(
        sim_driver,
        {
            f"{prefix}region_name": partial_reading(region.name),
            f"{prefix}energy_mode": partial_reading(region.energy_mode),
            f"{prefix}acquisition_mode": partial_reading(region.acquisition_mode),
            f"{prefix}lens_mode": partial_reading(region.lens_mode),
            f"{prefix}low_energy": partial_reading(
                to_kinetic_energy(region.low_energy, region.energy_mode, energy)
            ),
            f"{prefix}centre_energy": partial_reading(ANY),
            f"{prefix}high_energy": partial_reading(
                to_kinetic_energy(region.high_energy, region.energy_mode, energy)
            ),
            f"{prefix}energy_step": partial_reading(ANY),
            f"{prefix}pass_energy": partial_reading(region.pass_energy),
            f"{prefix}slices": partial_reading(region.slices),
            f"{prefix}acquire_time": partial_reading(region.acquire_time),
            f"{prefix}iterations": partial_reading(region.iterations),
            f"{prefix}total_steps": partial_reading(ANY),
            f"{prefix}total_time": partial_reading(ANY),
            f"{prefix}energy_axis": partial_reading(ANY),
            f"{prefix}binding_energy_axis": partial_reading(ANY),
            f"{prefix}angle_axis": partial_reading(ANY),
            f"{prefix}snapshot_values": partial_reading(region.values),
            f"{prefix}psu_mode": partial_reading(region.psu_mode),
            f"{prefix}cached_excitation_energy": partial_reading(0),
        },
    )


async def assert_analyser_vgscienta_configuration(
    sim_analyser: VGScientaDetector, region: VGScientaRegion
) -> None:
    sim_driver = sim_analyser.driver
    energy = await sim_analyser._controller.energy_source.energy.get_value()
    prefix = sim_driver.name + "-"
    await assert_configuration(
        sim_driver,
        {
            f"{prefix}region_name": partial_reading(region.name),
            f"{prefix}energy_mode": partial_reading(region.energy_mode),
            f"{prefix}acquisition_mode": partial_reading(region.acquisition_mode),
            f"{prefix}lens_mode": partial_reading(region.lens_mode),
            f"{prefix}low_energy": partial_reading(
                to_kinetic_energy(region.low_energy, region.energy_mode, energy)
            ),
            f"{prefix}centre_energy": partial_reading(
                to_kinetic_energy(region.centre_energy, region.energy_mode, energy)
            ),
            f"{prefix}high_energy": partial_reading(
                to_kinetic_energy(region.high_energy, region.energy_mode, energy)
            ),
            f"{prefix}energy_step": partial_reading(region.energy_step),
            f"{prefix}pass_energy": partial_reading(region.pass_energy),
            f"{prefix}slices": partial_reading(region.slices),
            f"{prefix}iterations": partial_reading(region.iterations),
            f"{prefix}total_steps": partial_reading(ANY),
            f"{prefix}acquire_time": partial_reading(region.acquire_time),
            f"{prefix}total_time": partial_reading(ANY),
            f"{prefix}energy_axis": partial_reading(ANY),
            f"{prefix}binding_energy_axis": partial_reading(ANY),
            f"{prefix}angle_axis": partial_reading(ANY),
            f"{prefix}detector_mode": partial_reading(region.detector_mode),
            f"{prefix}region_min_x": partial_reading(region.min_x),
            f"{prefix}region_size_x": partial_reading(region.size_x),
            f"{prefix}sensor_max_size_x": partial_reading(ANY),
            f"{prefix}region_min_y": partial_reading(region.min_y),
            f"{prefix}region_size_y": partial_reading(region.size_y),
            f"{prefix}sensor_max_size_y": partial_reading(ANY),
            f"{prefix}psu_mode": partial_reading(ANY),
            f"{prefix}cached_excitation_energy": partial_reading(0),
        },
    )
