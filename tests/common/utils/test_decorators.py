from collections.abc import Mapping

import pytest
from bluesky.plan_stubs import sleep
from bluesky.plans import count
from bluesky.run_engine import RunEngine

from sm_bluesky.common.sim_devices import SimStage
from sm_bluesky.common.utils.decorators import (
    add_default_metadata,
    add_extra_names_to_meta,
    auto_type_cast,
)

DEFAULT_METADATA = {
    "energy": {"value": 1.8, "unit": "eV"},
    "detector_dist": {"value": 88, "unit": "mm"},
}


async def test_add_meta_success_with_no_meta(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict]],
    sim_stage_step: SimStage,
) -> None:
    count_meta = add_default_metadata(count, DEFAULT_METADATA)

    run_engine(
        count_meta([sim_stage_step.x]),
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
    sim_stage_step: SimStage,
) -> None:
    count_meta = add_default_metadata(count, DEFAULT_METADATA)
    run_engine(
        count_meta([sim_stage_step.x], md={"bah": "bah"}),
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
    sim_stage_step: SimStage,
) -> None:
    count_meta = add_default_metadata(count)

    run_engine(count_meta([sim_stage_step.x]))
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


class TestCasting:
    @auto_type_cast
    def set_params(
        self,
        integer: int = 1,
        double: float = 5.0,
        string: str = "string",
    ):
        return integer, double, string


@pytest.fixture
def test_casting():
    return TestCasting()


def test_auto_type_cast_default(test_casting: TestCasting):
    interger, number, string = test_casting.set_params()

    assert interger == 1
    assert number == 5
    assert string == "string"
    assert isinstance(interger, int)
    assert isinstance(number, float)
    assert isinstance(string, str)


def test_cast_invalid(test_casting: TestCasting):
    with pytest.raises(TypeError, match="Argument 'integer' casting failed"):
        test_casting.set_params(b"not_an_int", b"1.0", b"test")  # pyright: ignore[reportArgumentType]


@pytest.mark.parametrize(
    "test_input, expected_result",
    [
        ([b"5", b"6.5", b"hello"], (5, 6.5, "hello")),
        ([b"10", b"0.0", b"world"], (10, 0.0, "world")),
        ([b"1", b"1.1"], (1, 1.1, "string")),
        ([b"1"], (1, 5, "string")),
    ],
)
def test_auto_type_cast_multi(test_input, expected_result, test_casting: TestCasting):
    result = test_casting.set_params(*test_input)
    assert result == expected_result
