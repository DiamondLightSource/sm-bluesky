from collections import defaultdict

from bluesky.plans import count
from bluesky.run_engine import RunEngine
from dodal.devices.motors import XYZStage

from sm_bluesky.common.helper.add_meta import add_default_metadata

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

    def capture_emitted(name, doc):
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
