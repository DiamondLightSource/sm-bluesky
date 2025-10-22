from collections.abc import Mapping

import pytest
from bluesky.plan_stubs import sleep
from bluesky.plans import count
from bluesky.run_engine import RunEngine
from dodal.devices.motors import XYZStage

from sm_bluesky.common.helper.add_meta import (
    add_default_metadata,
    add_extra_names_to_meta,
)

DEFAULT_METADATA = {
    "energy": {"value": 1.8, "unit": "eV"},
    "detector_dist": {"value": 88, "unit": "mm"},
}


async def test_add_meta_success_with_no_meta(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    sim_motor_step: XYZStage,
) -> None:
    count_meta = add_default_metadata(count, DEFAULT_METADATA)

    run_engine(
        count_meta([sim_motor_step.x]),
    )
    assert run_engine_documents["start"][0]["energy"] == DEFAULT_METADATA["energy"]
    assert (
        run_engine_documents["start"][0]["detector_dist"]
        == DEFAULT_METADATA["detector_dist"]
    )
    assert run_engine_documents["start"][0]["plan_name"] == "count"


async def test_add_meta_success_with_meta(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    sim_motor_step: XYZStage,
) -> None:
    count_meta = add_default_metadata(count, DEFAULT_METADATA)
    run_engine(
        count_meta([sim_motor_step.x], md={"bah": "bah"}),
    )
    assert run_engine_documents["start"][0]["energy"] == DEFAULT_METADATA["energy"]
    assert (
        run_engine_documents["start"][0]["detector_dist"]
        == DEFAULT_METADATA["detector_dist"]
    )
    assert run_engine_documents["start"][0]["bah"] == "bah"
    assert run_engine_documents["start"][0]["plan_name"] == "count"


async def test_add_meta_success_with_no_extra_meta(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    sim_motor_step: XYZStage,
) -> None:
    count_meta = add_default_metadata(count)

    run_engine(count_meta([sim_motor_step.x]))
    assert run_engine_documents["start"][0]["plan_name"] == "count"


def some_plan(md: float):
    yield from sleep(md)


async def test_add_meta_fail(
    run_engine: RunEngine,
) -> None:
    count_meta = add_default_metadata(some_plan, DEFAULT_METADATA)

    with pytest.raises(ValueError, match="md is reserved for meta data."):
        run_engine(count_meta(md=1), wait=True)


def test_add_extra_names_to_meta_with_empty_dictionary() -> None:
    md = {}
    md = add_extra_names_to_meta(md=md, key="Bound", names=["James"])

    assert md == {"Bound": ["James"]}


def test_add_extra_names_to_meta_dictionary() -> None:
    md = {"Bound": ["Hun"]}
    print(md)
    md = add_extra_names_to_meta(md=md, key="Bound", names=["James", "more"])

    print(md)
    assert md == {"Bound": ["Hun", "James", "more"]}


def test_add_extra_names_to_meta_dictionary_fail_value_not_list() -> None:
    md = {"Bound": some_plan}
    with pytest.raises(TypeError):
        md = add_extra_names_to_meta(md=md, key="Bound", names=["James"])
