from pathlib import Path

from bluesky import RunEngine
from dodal.common.beamlines.beamline_utils import get_path_provider, set_path_provider
from dodal.common.visit import (
    LocalDirectoryServiceClient,
    StaticVisitPathProvider,
)
from ophyd_async.fastcs.panda import HDFPanda
from ophyd_async.plan_stubs import ensure_connected

from sm_bluesky.beamlines.p99.plans.sample_stage_scanning import trajectory_fly_scan

set_path_provider(
    StaticVisitPathProvider(
        "p99",
        Path("/dls/p99/data/2024/cm37284-2/processing/writenData"),
        client=LocalDirectoryServiceClient(),  # RemoteDirectoryServiceClient("http://p99-control:8088/api"),
    )
)


def panda() -> HDFPanda:
    return HDFPanda(
        "BL99P-MO-PANDA-01:", path_provider=get_path_provider(), name="panda1"
    )


p = panda()

RE = RunEngine()
RE(ensure_connected(p))
RE(
    trajectory_fly_scan(
        slow_start=1,
        slow_stop=2,
        slow_num=10,
        fast_start=0,
        fast_stop=1,
        fast_num=10,
        duration=1,
        panda=p,
    )
)
