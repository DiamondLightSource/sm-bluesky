import pytest
from dodal.devices.electron_analyser.vgscienta import VGScientaRegion
from ophyd_async.core import DeviceVector, init_devices
from ophyd_async.epics.motor import Motor

from sm_bluesky.common.electron_analyser.energy_source import (
    get_energy_source_for_region,
)


@pytest.fixture
async def dcmenergy() -> Motor:
    async with init_devices(mock=True, connect=True):
        dcmenergy = Motor("TEST-DCM:")
    return dcmenergy


@pytest.fixture
async def pgmenergy() -> Motor:
    async with init_devices(mock=True, connect=True):
        pgmenergy = Motor("TEST-PGM:")
    return pgmenergy


@pytest.fixture
async def energy_sources(pgmenergy: Motor, dcmenergy: Motor) -> DeviceVector[Motor]:
    async with init_devices(mock=True, connect=True):
        energy_source = DeviceVector({0: dcmenergy, 1: pgmenergy})
    return energy_source


def test_energy_source_for_region_has_region_select_source1_is_valid(
    energy_sources, dcmenergy
) -> None:
    region = VGScientaRegion(excitation_energy_source="source1")
    energy_source = get_energy_source_for_region(region, energy_sources)
    assert energy_source == dcmenergy


def test_energy_source_for_region_has_region_select_source2_is_valid(
    energy_sources, pgmenergy
) -> None:
    region = VGScientaRegion(excitation_energy_source="source2")
    energy_source = get_energy_source_for_region(region, energy_sources)
    assert energy_source == pgmenergy


def test_energy_source_for_region_has_region_select_invalid_source_is_invalid(
    energy_sources,
) -> None:
    region = VGScientaRegion(excitation_energy_source="invalid_source")
    with pytest.raises(KeyError):
        get_energy_source_for_region(region, energy_sources)
