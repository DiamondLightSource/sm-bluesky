import json
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from blueapi.config import ApplicationConfig
from blueapi.core import DataEvent

from sm_bluesky.common.cli import load_config
from sm_bluesky.common.clients.blueapi_session import BlueAPISession


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


@pytest.fixture
def mock_client_class():
    with patch("sm_bluesky.common.clients.blueapi_session.BlueapiClient") as mock_cls:
        yield mock_cls


@pytest.fixture
def mock_secho():
    with patch("sm_bluesky.common.clients.blueapi_session.click.secho") as mock:
        yield mock


@pytest.fixture
def mock_echo():
    with patch("sm_bluesky.common.clients.blueapi_session.click.echo") as mock:
        yield mock


@pytest.fixture
def session(
    mock_client_class: MagicMock, mock_secho: MagicMock, mock_echo: MagicMock
) -> BlueAPISession:
    session = BlueAPISession(config=ApplicationConfig())
    mock_secho.reset_mock()
    mock_echo.reset_mock()
    return session


def test_blueapi_session_initialisation_with_instrument_session(
    mock_echo: MagicMock, mock_secho: MagicMock, mock_client_class: MagicMock
) -> None:
    mock_client = mock_client_class.from_config.return_value
    mock_client.plans = [MagicMock(name="plan1")]
    mock_client.plans[0].name = "plan1"
    mock_client.devices = [MagicMock(name="dev1")]
    mock_client.devices[0].name = "dev1"

    config = ApplicationConfig()

    BlueAPISession(config=config, instrument_session="my-session")

    mock_client_class.from_config.assert_called_once_with(config)
    mock_client.login.assert_called_once()
    assert mock_client.instrument_session == "my-session"

    mock_echo.assert_any_call("Active instrument session: my-session")
    mock_secho.assert_not_called()


def test_blueapi_session_initialisation_without_instrument_session(
    mock_secho: MagicMock, mock_client_class: MagicMock
) -> None:
    BlueAPISession(config=ApplicationConfig())

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
    assert "run" in kwargs["user_ns"]
    assert kwargs["user_ns"]["bc"] is session.bc
    assert kwargs["user_ns"]["run"] == session.run


def test_callbacks_handling(
    mock_echo: MagicMock, session: BlueAPISession, mock_client_class: MagicMock
) -> None:
    mock_client = mock_client_class.from_config.return_value
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


def test_callback_scan_id_collision(
    mock_echo: MagicMock, session: BlueAPISession, mock_client_class: MagicMock
) -> None:
    mock_client = mock_client_class.from_config.return_value
    callback = mock_client.add_callback.call_args[0][0]

    for i, expected_id in enumerate(("scan1", "scan1_1", "scan1_2")):
        callback(
            DataEvent(
                name="start",
                doc={"scan_id": "scan1", "uid": f"uid{i}", "time": 0},
                task_id=f"task{i}",
            )
        )
        assert session.current_scan_id == expected_id
        assert expected_id in session.data
        mock_echo.assert_any_call(
            f"1970-01-01 00:00:00 - Run started (scan_id={expected_id}, uid=uid{i})"
        )


def test_callback_event_without_scan_id(
    mock_echo: MagicMock, session: BlueAPISession, mock_client_class: MagicMock
) -> None:
    mock_client = mock_client_class.from_config.return_value
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

        fig = FakeFig()

    class FakeDeadPlot:
        class FakeFig:
            number = 2

        fig = FakeFig()

    session._active_plot_windows = [FakePlot(), FakeDeadPlot()]  # type: ignore

    with (
        patch(
            "sm_bluesky.common.clients.blueapi_session.InteractivePlotWindow"
        ) as mock_win,
        patch(
            "sm_bluesky.common.clients.blueapi_session.plt.fignum_exists",
            side_effect=lambda num: num == 1,
        ),
    ):
        session.plot("scan1")
        assert len(session._active_plot_windows) == 2
        mock_win.assert_called_once()


def test_blueapi_session_scan_caching(
    mock_client_class: MagicMock, tmp_path: Path
) -> None:
    mock_client = mock_client_class.from_config.return_value
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
    assert json.loads(cache_file.read_text().strip()) == {"888": {"motor": [10]}}

    session2 = BlueAPISession(config=config, instrument_session="test-session")
    assert "888" in session2.data
    assert session2.data["888"]["motor"] == [10]


def test_blueapi_session_corrupt_scan_cache(
    mock_client_class: MagicMock, tmp_path: Path
) -> None:

    cache_dir = tmp_path / ".sm-bluesky" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "bad-session_scans.jsonl"
    cache_file.write_text("invalid json format {")

    config = ApplicationConfig()
    session = BlueAPISession(config=config, instrument_session="bad-session")
    assert session.data == {}


def test_blueapi_session_no_instrument_session_cache_bypassed(
    session: BlueAPISession,
) -> None:
    session.bc.instrument_session = None  # type: ignore
    assert session._get_cache_path() is None
    session._load_scan_cache()
    session._save_scan_to_cache("123")


@patch("builtins.open", side_effect=Exception("Mock write error"))
def test_blueapi_session_write_cache_error(
    mock_open: MagicMock,
    mock_client_class: MagicMock,
    tmp_path: Path,
) -> None:

    config = ApplicationConfig()
    session = BlueAPISession(config=config, instrument_session="err-session")
    session.data["123"] = {"motor": [10]}

    with patch("click.echo") as mock_echo:
        session._save_scan_to_cache("123")
        mock_echo.assert_called_once_with(
            "Warning: Could not write to scan cache: Mock write error"
        )


@patch("builtins.open")
def test_blueapi_session_save_cache_missing_scan_id(
    mock_open: MagicMock,
    mock_client_class: MagicMock,
) -> None:
    config = ApplicationConfig()
    session = BlueAPISession(config=config, instrument_session="test-session")
    session._save_scan_to_cache("missing-scan-id")
    mock_open.assert_not_called()


def test_run_task_updates_and_flushes_plots_during_scan(
    mock_client_class: MagicMock,
) -> None:

    mock_client = mock_client_class.from_config.return_value
    unblock_task = threading.Event()

    def slow_task(*args, **kwargs):
        unblock_task.wait(timeout=5.0)
        return "task_done"

    mock_client.run_task = slow_task
    session = BlueAPISession(config=ApplicationConfig())

    active_win = MagicMock()
    active_win.fig.number = 1
    dead_win = MagicMock()
    dead_win.fig.number = 2
    session._active_plot_windows = [active_win, dead_win]

    monotonic_vals = iter([1.0, 1.2])
    sleep_calls = 0

    def fake_sleep(_: float) -> None:
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls >= 2:
            unblock_task.set()

    with (
        patch(
            "sm_bluesky.common.clients.blueapi_session.plt.fignum_exists",
            side_effect=lambda num: num == 1,
        ),
        patch(
            "sm_bluesky.common.clients.blueapi_session.time.monotonic",
            side_effect=lambda: next(monotonic_vals, 2.5),
        ),
        patch(
            "sm_bluesky.common.clients.blueapi_session.time.sleep",
            side_effect=fake_sleep,
        ),
    ):
        result = session.bc.run_task(MagicMock())

    assert result == "task_done"
    assert session._active_plot_windows == [active_win]
    assert active_win.update_plot.call_count >= 2
    assert active_win.fig.canvas.flush_events.call_count >= 3
    dead_win.update_plot.assert_not_called()


def test_run_script_with_ipython(session: BlueAPISession, tmp_path: Path) -> None:
    script = tmp_path / "my_scans.py"
    script.write_text("x = 1\n")
    mock_ip = MagicMock()

    with patch(
        "IPython.core.getipython.get_ipython",
        return_value=mock_ip,
    ):
        session.run(script)

    mock_ip.run_line_magic.assert_called_once_with("run", f'-i "{script.resolve()}"')


def test_run_script_missing_file(
    mock_secho: MagicMock, session: BlueAPISession, tmp_path: Path
) -> None:
    missing = tmp_path / "nonexistent.py"
    session.run(missing)
    mock_secho.assert_called_once_with(
        f"Error: Script not found: {missing.resolve()}", fg="red"
    )


def test_run_script_syntax_error(
    mock_secho: MagicMock, session: BlueAPISession, tmp_path: Path
) -> None:
    bad_script = tmp_path / "bad_syntax.py"
    bad_script.write_text("def broken(:\nthis is the best script in the world")

    session.run(bad_script)

    assert mock_secho.call_count == 1
    assert f"Error in script {bad_script.resolve()}:" in mock_secho.call_args.args[0]
    assert mock_secho.call_args.kwargs == {"fg": "red"}


def test_run_script_runtime_error(
    mock_secho: MagicMock, session: BlueAPISession, tmp_path: Path
) -> None:
    err_script = tmp_path / "runtime_err.py"
    err_script.write_text("x = 1\n")
    mock_ip = MagicMock()
    mock_ip.run_line_magic.side_effect = RuntimeError("boom")

    with patch("IPython.core.getipython.get_ipython", return_value=mock_ip):
        session.run(err_script)

    mock_secho.assert_called_once_with(
        f"Error executing script {err_script.resolve()}: boom", fg="red"
    )


def test_run_script_no_active_session(
    mock_secho: MagicMock, session: BlueAPISession, tmp_path: Path
) -> None:
    script = tmp_path / "script.py"
    script.write_text("x = 1\n")

    with patch("IPython.core.getipython.get_ipython", return_value=None):
        session.run(script)

    mock_secho.assert_called_once_with(
        f"Error: Cannot execute script {script.resolve()}: No active session found.",
        fg="red",
    )
