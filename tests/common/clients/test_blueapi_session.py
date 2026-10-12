import json
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from blueapi.config import ApplicationConfig
from blueapi.core import DataEvent

from sm_bluesky.common.cli import load_config
from sm_bluesky.common.clients.blueapi_session import BlueAPISession


@pytest.fixture
def mock_blueapi_client() -> Generator[MagicMock, None, None]:
    with patch("sm_bluesky.common.clients.blueapi_session.BlueapiClient") as mock_cls:
        yield mock_cls


@pytest.fixture
def session(mock_blueapi_client: MagicMock) -> BlueAPISession:
    config = ApplicationConfig()
    return BlueAPISession(config=config, instrument_session="test-session")


def test_load_config_with_path(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("api:\n  url: http://localhost:8000")

    config = load_config(config_path=config_file)

    assert isinstance(config, ApplicationConfig)
    assert str(config.api.url) == "http://localhost:8000/"


def test_load_config_with_beamline() -> None:
    config = load_config(beamline="i10")

    assert isinstance(config, ApplicationConfig)
    assert str(config.api.url) == "https://i10-blueapi.diamond.ac.uk/"
    assert str(config.stomp.url) == "tcp://i10-rabbitmq-daq.diamond.ac.uk:61613"
    assert config.stomp.enabled is True


def test_load_config_without_args_raises_error() -> None:
    with pytest.raises(ValueError, match="No beamline specified"):
        load_config()


@patch("sm_bluesky.common.clients.blueapi_session.click.echo")
@patch("sm_bluesky.common.clients.blueapi_session.click.secho")
def test_blueapi_session_initialisation_with_instrument_session(
    mock_secho: MagicMock,
    mock_echo: MagicMock,
    mock_blueapi_client: MagicMock,
) -> None:
    mock_client = mock_blueapi_client.from_config.return_value
    mock_client.plans = [MagicMock(name="plan1")]
    mock_client.plans[0].name = "plan1"
    mock_client.devices = [MagicMock(name="dev1")]
    mock_client.devices[0].name = "dev1"

    config = ApplicationConfig()

    BlueAPISession(config=config, instrument_session="my-session")

    mock_blueapi_client.from_config.assert_called_once_with(config)
    mock_client.login.assert_called_once()
    assert mock_client.instrument_session == "my-session"

    mock_echo.assert_any_call("Active instrument session: my-session")
    mock_secho.assert_not_called()


@patch("sm_bluesky.common.clients.blueapi_session.click.secho")
def test_blueapi_session_initialisation_without_instrument_session(
    mock_secho: MagicMock,
    mock_blueapi_client: MagicMock,
) -> None:
    config = ApplicationConfig()

    BlueAPISession(config=config)

    mock_secho.assert_called_once_with(
        "\n[Notice] No instrument session set."
        " Set `bc.instrument_session = '<session_id>'` before dispatching plans.",
        fg="red",
    )


@patch("IPython.start_ipython")
def test_start_shell(mock_start: MagicMock, session: BlueAPISession) -> None:
    session.start_shell()
    mock_start.assert_called_once()
    kwargs = mock_start.call_args.kwargs
    assert "bc" in kwargs["user_ns"]
    assert "pl" in kwargs["user_ns"]
    assert "dev" in kwargs["user_ns"]
    assert "scan_data" in kwargs["user_ns"]
    assert "metadata" in kwargs["user_ns"]
    assert "get_detector_filepath" in kwargs["user_ns"]
    assert kwargs["user_ns"]["bc"] is session.bc


@patch("sm_bluesky.common.clients.blueapi_session.click.echo")
def test_callbacks_handling(
    mock_echo: MagicMock,
    session: BlueAPISession,
    mock_blueapi_client: MagicMock,
) -> None:
    mock_client = mock_blueapi_client.from_config.return_value
    mock_client.add_callback.assert_called_once()
    callback = mock_client.add_callback.call_args[0][0]

    start_event = DataEvent(
        name="start",
        doc={"scan_id": "scan1", "uid": "uid1", "time": 0},
        task_id="task1",
    )
    callback(start_event)
    assert session.current_scan_id == "scan1"
    assert "scan1" in session.data
    mock_echo.assert_any_call(
        "1970-01-01 00:00:00 - Run started (scan_id=scan1, uid=uid1)"
    )

    event = DataEvent(
        name="event",
        doc={"seq_num": 1, "data": {"motor1": 10.5}, "time": 1},
        task_id="task1",
    )
    callback(event)
    assert session.data["scan1"]["motor1"] == [10.5]
    mock_echo.assert_any_call("1970-01-01 00:00:01 - Point 1: motor1=10.5")

    stop_event = DataEvent(
        name="stop",
        doc={"exit_status": "success", "time": 2, "uid": "uid1"},
        task_id="task1",
    )
    callback(stop_event)
    assert session.current_scan_id is None
    mock_echo.assert_any_call(
        "1970-01-01 00:00:02 - Run complete (scan_id=scan1, uid: uid1): success"
    )


@patch("sm_bluesky.common.clients.blueapi_session.click.echo")
def test_callback_event_without_scan_id(
    mock_echo: MagicMock,
    session: BlueAPISession,
    mock_blueapi_client: MagicMock,
) -> None:
    mock_client = mock_blueapi_client.from_config.return_value
    callback = mock_client.add_callback.call_args[0][0]
    session.current_scan_id = None

    event = DataEvent(
        name="event",
        doc={"seq_num": 1, "data": {"motor1": 10.5}, "time": 1},
        task_id="task1",
    )
    callback(event)

    assert "1970-01-01 00:00:01 - Point 1: motor1=10.5" not in [
        call.args[0] for call in mock_echo.call_args_list
    ]


def test_dead_plot_window_removed(session: BlueAPISession) -> None:
    class FakePlot:
        class FakeFig:
            number = 1

        class FakePlt:
            @staticmethod
            def fignum_exists(num):
                return num == 1

        fig = FakeFig()
        plt = FakePlt()

    class FakeDeadPlot:
        class FakeFig:
            number = 2

        class FakePlt:
            @staticmethod
            def fignum_exists(num):
                return False

        fig = FakeFig()
        plt = FakePlt()

    session._active_plot_windows = [FakePlot(), FakeDeadPlot()]  # type: ignore

    with patch(
        "sm_bluesky.common.clients.blueapi_session.InteractivePlotWindow"
    ) as mock_win:
        session.plot("scan1")
        assert len(session._active_plot_windows) == 2
        mock_win.assert_called_once()


def test_plot_import_error(session: BlueAPISession) -> None:
    with patch(
        "sm_bluesky.common.clients.blueapi_session.InteractivePlotWindow",
        side_effect=ImportError("mock error"),
    ):
        session.plot()


def test_blueapi_session_scan_caching(
    mock_blueapi_client: MagicMock, tmp_path: Path
) -> None:
    mock_client = mock_blueapi_client.from_config.return_value
    config = ApplicationConfig()
    session1 = BlueAPISession(config=config, instrument_session="test-session")

    callback = mock_client.add_callback.call_args[0][0]

    callback(
        DataEvent(
            name="start",
            doc={"scan_id": 888, "uid": "uid1", "time": 0.0},
            task_id="task1",
        )
    )
    assert session1.data["888"] == {}
    assert session1.metadata["888"] == {
        "scan_id": 888,
        "uid": "uid1",
        "time": 0.0,
    }

    callback(
        DataEvent(
            name="event",
            doc={"seq_num": 1, "data": {"motor": 10}, "time": 0.0},
            task_id="task1",
        )
    )
    assert session1.data["888"]["motor"] == [10]

    callback(
        DataEvent(
            name="stop",
            doc={"exit_status": "success", "uid": "uid1", "time": 0.0},
            task_id="task1",
        )
    )
    cache_file = tmp_path / ".sm-bluesky" / "cache" / "test-session_scans.jsonl"
    assert cache_file.exists()
    assert json.loads(cache_file.read_text().strip()) == {
        "888": {
            "data": {"motor": [10]},
            "meta": {"scan_id": 888, "uid": "uid1", "time": 0.0},
        }
    }

    session2 = BlueAPISession(config=config, instrument_session="test-session")
    assert "888" in session2.data
    assert session2.data["888"]["motor"] == [10]
    assert session2.metadata["888"]["scan_id"] == 888

    with open(cache_file, "a") as f:
        f.write(json.dumps({"888": {"motor": [20]}}) + "\n")

    session3 = BlueAPISession(config=config, instrument_session="test-session")
    assert "888" in session3.data
    assert session3.data["888"]["motor"] == [20]


def test_blueapi_session_corrupt_scan_cache(
    mock_blueapi_client: MagicMock, tmp_path: Path
) -> None:
    cache_dir = tmp_path / ".sm-bluesky" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "bad-session_scans.jsonl"
    cache_file.write_text("invalid json format {")

    config = ApplicationConfig()
    session = BlueAPISession(config=config, instrument_session="bad-session")
    assert session.data == {}


def test_blueapi_session_no_instrument_session_cache_bypassed(
    mock_blueapi_client: MagicMock,
) -> None:
    config = ApplicationConfig()
    session = BlueAPISession(config=config, instrument_session=None)
    session.bc.instrument_session = None  # type: ignore
    assert session._get_cache_path() is None
    session._load_scan_cache()
    session._save_scan_to_cache("123")


@patch("builtins.open", side_effect=Exception("Mock write error"))
def test_blueapi_session_write_cache_error(
    mock_open: MagicMock,
    session: BlueAPISession,
) -> None:
    session.data["123"] = {"motor": [10]}

    with patch("click.echo") as mock_echo:
        session._save_scan_to_cache("123")
        mock_echo.assert_called_once_with(
            "Warning: Could not write to scan cache: Mock write error"
        )


@patch("builtins.open")
def test_blueapi_session_save_cache_missing_scan_id(
    mock_open: MagicMock,
    session: BlueAPISession,
) -> None:
    session._save_scan_to_cache("missing-scan-id")
    mock_open.assert_not_called()


def test_blueapi_session_metadata_capture(
    session: BlueAPISession,
    mock_blueapi_client: MagicMock,
) -> None:
    callback = mock_blueapi_client.from_config.return_value.add_callback.call_args[0][0]

    start_doc = {
        "scan_id": 180,
        "uid": "test-uid",
        "time": 8888888,
        "instrument": "p99",
        "data_session_directory": "/dls/p99/data/2026/cm44186-3",
        "detector_file_template": "{instrument}-{scan_id}-{device_name}",
    }
    callback(DataEvent(name="start", doc=start_doc, task_id="task1"))

    assert "180" in session.data
    assert session.data["180"] == {}
    assert "180" in session.metadata
    assert session.metadata["180"] == start_doc


def test_blueapi_session_get_detector_filepath_success(
    session: BlueAPISession,
) -> None:
    session.metadata["180"] = {
        "instrument": "p99",
        "data_session_directory": "/dls/p99/data/2026/cm44186-3",
        "detector_file_template": "{instrument}-{scan_id}-{device_name}",
    }
    session.current_scan_id = "180"

    path = session.get_detector_filepath("andor2_det")
    assert path == "/dls/p99/data/2026/cm44186-3/p99-180-andor2_det.h5"

    assert (
        session.get_detector_filepath("andor2_det", scan_id=180)
        == "/dls/p99/data/2026/cm44186-3/p99-180-andor2_det.h5"
    )
    assert (
        session.get_detector_filepath("andor2_det", scan_id="180")
        == "/dls/p99/data/2026/cm44186-3/p99-180-andor2_det.h5"
    )


def test_blueapi_session_get_detector_filepath_edge_cases(
    session: BlueAPISession,
) -> None:
    assert session.get_detector_filepath("andor2_det") is None

    session.metadata["bad_scan"] = {"instrument": "p99"}
    assert session.get_detector_filepath("andor2_det", scan_id="bad_scan") is None

    assert session.get_detector_filepath("andor2_det", scan_id="nonexistent") is None

    session.metadata["corrupt_template"] = {
        "instrument": "p99",
        "data_session_directory": "/data",
        "detector_file_template": "{random stuff",
    }
    assert (
        session.get_detector_filepath("andor2_det", scan_id="corrupt_template") is None
    )
