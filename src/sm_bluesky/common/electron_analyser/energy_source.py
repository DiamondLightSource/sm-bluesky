from dodal.devices.electron_analyser.abstract import (
    AbstractBaseRegion,
)
from ophyd_async.core import DeviceVector
from ophyd_async.epics.motor import Motor

# This is needed as a workaround until this is fixed
# https://github.com/bluesky/ophyd-async/issues/903
key_to_index = {"source1": 0, "source2": 1}


def get_energy_source_for_region(
    region: AbstractBaseRegion, energy_sources: DeviceVector[Motor]
) -> Motor:
    try:
        source_alias: str = region.excitation_energy_source
        return energy_sources[key_to_index[source_alias]]
    except KeyError as e:
        raise KeyError(
            f"Region {region.name} selected excitation energy"
            + f"{region.excitation_energy_source}. This isn't a "
            + f"valid source. Valid sources are {energy_sources.keys()}."
        ) from e
