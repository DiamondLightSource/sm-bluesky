import pytest
from blueapi.client.client import BlueapiClient
from blueapi.config import ApplicationConfig, RestConfig, StompConfig
from blueapi.worker.task import Task
from bluesky_stomp.models import BasicAuthentication
from pydantic import HttpUrl


@pytest.fixture
def task_definition() -> dict[str, Task]:
    return {
        "count": Task(name="count", params={"detectors": ["andor2_point"]}),
        "stxm_step": Task(
            name="stxm_step",
            params={
                "dets": ["andor2_point"],
                "count_time": 0.1,
                "x_step_motor": "sample_stage.x",
                "x_step_start": -0.1,
                "x_step_end": 0.1,
                "x_step_size": 0.05,
                "y_step_motor": "sample_stage.y",
                "y_step_start": -0.1,
                "y_step_end": 0.1,
                "y_step_size": 0.05,
            },
        ),
        "stxm_fast": Task(
            name="stxm_fast",
            params={
                "dets": ["andor2_point"],
                "count_time": 0.1,
                "step_motor": "sample_stage.x",
                "step_start": -0.1,
                "step_end": 0.1,
                "scan_motor": "sample_stage.y",
                "scan_start": -0.1,
                "scan_end": 0.1,
                "plan_time": 15,
            },
        ),
    }


def pytest_addoption(parser: pytest.Parser):
    parser.addoption("--password", action="store", default="")


@pytest.fixture
def config(request: pytest.FixtureRequest) -> ApplicationConfig:
    password = request.config.getoption("--password")
    return ApplicationConfig(
        stomp=StompConfig(
            enabled=True,
            url=HttpUrl("http://172.23.177.208"),
            auth=BasicAuthentication(username="p99", password=password),  # type: ignore
        ),
        api=RestConfig(url=HttpUrl("https://p99-blueapi.diamond.ac.uk:443")),
    )


# This client will use authentication if a valid cached token is found
@pytest.fixture
def client(config: ApplicationConfig) -> BlueapiClient:
    return BlueapiClient.from_config(config=config)
