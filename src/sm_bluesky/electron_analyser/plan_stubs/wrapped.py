from typing import Any, get_args, get_origin

from bluesky.plan_stubs import mv
from bluesky.utils import MsgGenerator, plan
from dodal.devices.electron_analyser.base import (
    AbstractAnalyserDriverIO,
    AbstractBaseRegion,
    AbstractBaseSequence,
    ElectronAnalyserDetector,
)
from dodal.devices.electron_analyser.specs import SpecsRegion
from dodal.devices.electron_analyser.vgscienta import VGScientaRegion


def _get_region_type_from_detector(
    obj: ElectronAnalyserDetector,
) -> type[AbstractBaseRegion]:
    for base in type(obj).__orig_bases__:  # type: ignore
        if get_origin(base) is ElectronAnalyserDetector:
            _, region_type = get_args(base)
            # This can be simplified if we implement concrete types of region.
            driver = obj.driver  # type:ignore
            region_type = _add_region_parameterisation(driver, region_type)
            return region_type

    raise ValueError(f"Unable to determine the region type from object {obj}.")


def _add_region_parameterisation(
    driver: AbstractAnalyserDriverIO, region_type: type[AbstractBaseRegion]
) -> type[AbstractBaseRegion]:
    lens_mode_type = driver.lens_mode_type
    pass_energy_type = driver.pass_energy_type
    psu_mode_type = driver.psu_mode_type
    # Must reparametrize type to work.
    if region_type is VGScientaRegion:
        region_type = region_type[lens_mode_type, pass_energy_type]  # type: ignore
    elif region_type is SpecsRegion:
        region_type = region_type[lens_mode_type, psu_mode_type]  # type: ignore

    return region_type


def dict_to_sequence(
    analyser: ElectronAnalyserDetector, seq_dict: dict[str, Any]
) -> AbstractBaseSequence:
    regions: list[AbstractBaseRegion] = []
    regions_dict = seq_dict["regions"]
    for region_dict in regions_dict:
        region_type = _get_region_type_from_detector(analyser)
        region = region_type.model_validate(region_dict)
        regions.append(region)

    return AbstractBaseSequence(regions=regions)


@plan
def set_region(
    analyser: ElectronAnalyserDetector,
    region: dict[str, Any] | AbstractBaseRegion,
) -> MsgGenerator:
    """
    Wrapped move plan that will convert a python dictionary to a valid pydantic model
    of a region to pass to the electron analyser detector. Needed so comptaible with
    BlueAPI as it currently doesn't support pydantic models.
    """
    if isinstance(region, dict):
        region_type = _get_region_type_from_detector(analyser)
        region = region_type.model_validate(region)

    yield from mv(analyser, region)
