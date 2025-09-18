from collections import defaultdict
from typing import Any

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
    RE: RunEngine,
    sim_motor_step: XYZStage,
):
    count_meta = add_default_metadata(count, DEFAULT_METADATA)
    docs = defaultdict(list)

    def capture_emitted(name: str, doc: Any) -> None:
        docs[name].append(doc)

    RE(
        count_meta([sim_motor_step.x]),
        capture_emitted,
    )
    assert docs["start"][0]["energy"] == DEFAULT_METADATA["energy"]
    assert docs["start"][0]["detector_dist"] == DEFAULT_METADATA["detector_dist"]
    assert docs["start"][0]["plan_name"] == "count"


async def test_add_meta_success_with_meta(
    RE: RunEngine,
    sim_motor_step: XYZStage,
):
    count_meta = add_default_metadata(count, DEFAULT_METADATA)
    docs = defaultdict(list)

    def capture_emitted(name, doc):
        docs[name].append(doc)

    RE(
        count_meta([sim_motor_step.x], md={"bah": "bah"}),
        capture_emitted,
    )
    assert docs["start"][0]["energy"] == DEFAULT_METADATA["energy"]
    assert docs["start"][0]["detector_dist"] == DEFAULT_METADATA["detector_dist"]
    assert docs["start"][0]["bah"] == "bah"
    assert docs["start"][0]["plan_name"] == "count"


async def test_add_meta_success_with_no_extra_meta(
    RE: RunEngine,
    sim_motor_step: XYZStage,
):
    count_meta = add_default_metadata(count)
    docs = defaultdict(list)

    def capture_emitted(name, doc):
        docs[name].append(doc)

    RE(
        count_meta([sim_motor_step.x]),
        capture_emitted,
    )
    assert docs["start"][0]["plan_name"] == "count"


def some_plan(md: float):
    yield from sleep(md)


async def test_add_meta_fail(
    RE: RunEngine,
):
    count_meta = add_default_metadata(some_plan, DEFAULT_METADATA)
    docs = defaultdict(list)

    def capture_emitted(name, doc):
        docs[name].append(doc)

    with pytest.raises(ValueError, match="md is reserved for meta data."):
        RE(count_meta(md=1), capture_emitted, wait=True)


def test_add_extra_names_to_meta_with_empty_dictionary():
    md = {}
    md = add_extra_names_to_meta(md=md, key="Bound", names=["James"])

    assert md == {"Bound": ["James"]}


def test_add_extra_names_to_meta_dictionary():
    md = {"Bound": ["Hun"]}
    print(md)
    md = add_extra_names_to_meta(md=md, key="Bound", names=["James", "more"])

    print(md)
    assert md == {"Bound": ["Hun", "James", "more"]}


def test_add_extra_names_to_meta_dictionary_fail_value_not_list():
    md = {"Bound": some_plan}
    with pytest.raises(TypeError):
        md = add_extra_names_to_meta(md=md, key="Bound", names=["James"])
