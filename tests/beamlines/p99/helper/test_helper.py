from collections import defaultdict

from bluesky.plans import count
from bluesky.run_engine import RunEngine
from dodal.devices.motors import XYZPositioner

from sm_bluesky.beamlines.p99.helper.add_meta import add_default_metadata

P99_DEFAULT_METADATA = {"energy": 1.8, "detector_dist": 88}


async def test_add_meta_success_with_no_meta(
    RE: RunEngine,
    sim_motor_step: XYZPositioner,
):
    count_meta = add_default_metadata(count)
    docs = defaultdict(list)

    def capture_emitted(name, doc):
        docs[name].append(doc)

    RE(
        count_meta([sim_motor_step.x]),
        capture_emitted,
    )
    assert docs["start"][0]["energy"] == P99_DEFAULT_METADATA["energy"]
    assert docs["start"][0]["detector_dist"] == P99_DEFAULT_METADATA["detector_dist"]


async def test_add_meta_success_with_meta(
    RE: RunEngine,
    sim_motor_step: XYZPositioner,
):
    count_meta = add_default_metadata(count)
    docs = defaultdict(list)

    def capture_emitted(name, doc):
        docs[name].append(doc)

    RE(
        count_meta([sim_motor_step.x], md={"bah": "bah"}),
        capture_emitted,
    )
    assert docs["start"][0]["energy"] == P99_DEFAULT_METADATA["energy"]
    assert docs["start"][0]["detector_dist"] == P99_DEFAULT_METADATA["detector_dist"]
    assert docs["start"][0]["bah"] == "bah"
