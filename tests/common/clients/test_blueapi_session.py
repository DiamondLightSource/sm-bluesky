import json
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from blueapi.config import ApplicationConfig
from blueapi.core import DataEvent

from sm_bluesky.common.cli import load_config
from sm_bluesky.common.clients.blueapi_session import (
    BlueAPISession,
    FitResult,
    LastFit,
)


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


@pytest.fixture
def callback(session: BlueAPISession, mock_client_class: MagicMock):
    mock_client = mock_client_class.from_config.return_value
    return mock_client.add_callback.call_args[0][0]


def _start_event(
    scan_id: str | int = "scan1",
    uid: str = "uid1",
    time: float = 0,
    task_id: str = "task1",
) -> DataEvent:
    return DataEvent(
        name="start",
        doc={"scan_id": scan_id, "uid": uid, "time": time},
        task_id=task_id,
    )


def _data_event(
    data: dict,
    seq_num: int = 1,
    time: float = 1,
    task_id: str = "task1",
) -> DataEvent:
    return DataEvent(
        name="event",
        doc={"seq_num": seq_num, "data": data, "time": time},
        task_id=task_id,
    )


def _stop_event(
    status: str = "success",
    uid: str = "uid1",
    time: float = 2,
    task_id: str = "task1",
) -> DataEvent:
    return DataEvent(
        name="stop",
        doc={"exit_status": status, "time": time, "uid": uid},
        task_id=task_id,
    )


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
    assert mock_start.call_args.kwargs["user_ns"] == {
        "bc": session.bc,
        "pl": session.bc.plans,
        "show_plan": session.print_plans,
        "dev": session.bc.devices,
        "show_devices": session.print_devices,
        "scan_data": session.data,
        "plot": session.plot,
        "run": session.run,
        "fit_scan": session.fit_scan,
        "set_fit_axes": session.set_fit_axes,
        "last_fit": session.last_fit,
    }


def test_callbacks_handling(
    mock_echo: MagicMock, session: BlueAPISession, callback
) -> None:
    callback(_start_event())
    assert session.current_scan_id == "scan1"
    assert "scan1" in session.data
    mock_echo.assert_any_call(
        "1970-01-01 00:00:00 - Run started (scan_id=scan1, uid=uid1)"
    )

    callback(_data_event({"motor1": 10.5}))
    assert session.data["scan1"]["motor1"] == [10.5]
    mock_echo.assert_any_call("1970-01-01 00:00:01 - Point 1: motor1=10.5")

    callback(_stop_event())
    assert session.current_scan_id is None
    mock_echo.assert_any_call(
        "1970-01-01 00:00:02 - Run complete (scan_id=scan1, uid: uid1): success"
    )


def test_callback_scan_id_collision(
    mock_echo: MagicMock, session: BlueAPISession, callback
) -> None:
    for i, expected_id in enumerate(("scan1", "scan1_1", "scan1_2")):
        callback(_start_event(scan_id="scan1", uid=f"uid{i}", task_id=f"task{i}"))
        assert session.current_scan_id == expected_id
        assert expected_id in session.data
        mock_echo.assert_any_call(
            f"1970-01-01 00:00:00 - Run started (scan_id={expected_id}, uid=uid{i})"
        )


def test_callback_event_without_scan_id(
    mock_echo: MagicMock, session: BlueAPISession, callback
) -> None:
    session.current_scan_id = None
    callback(_data_event({"motor1": 10.5}))

    assert "1970-01-01 00:00:01 - Point 1: motor1=10.5" not in [
        call.args[0] for call in mock_echo.call_args_list
    ]


def test_dead_plot_window_removed(session: BlueAPISession) -> None:
    active_win = MagicMock()
    active_win.fig.number = 1
    dead_win = MagicMock()
    dead_win.fig.number = 2
    session._active_plot_windows = [active_win, dead_win]

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

    callback(_start_event(scan_id=888, time=0.0))
    assert session1.data["888"] == {}

    callback(_data_event({"motor": 10}, time=0.0))
    assert session1.data["888"]["motor"] == [10]

    callback(_stop_event(time=0.0))
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


def test_set_fit_axes(session: BlueAPISession) -> None:
    assert session.preferred_x is None
    assert session.preferred_y is None
    session.set_fit_axes("motor1", "det1")
    assert session.preferred_x == "motor1"
    assert session.preferred_y == "det1"


@pytest.fixture
def gaussian_peak() -> tuple[list[float], list[float]]:
    x = np.linspace(0, 10, 21)
    y = 5.0 + 50.0 * np.exp(-((x - 5.0) ** 2) / (2 * 1.0**2))
    return x.tolist(), y.tolist()


def test_fit_scan_two_columns_and_default_scan_id(
    mock_echo: MagicMock,
    session: BlueAPISession,
    gaussian_peak: tuple[list[float], list[float]],
) -> None:
    x, y = gaussian_peak
    session.data["1"] = {"motor": x, "det": y}
    initial_last_fit = session.last_fit

    res = session.fit_scan()

    assert isinstance(res, FitResult)
    assert session.last_fit is initial_last_fit
    assert session.last_fit.centre == pytest.approx(5.0, abs=1e-2)
    assert session.last_fit.com == pytest.approx(5.0, abs=1e-2)
    assert session.last_fit.max_slope_x == pytest.approx(res.df.max_slope_x)
    assert session.last_fit.min_slope_x == pytest.approx(res.df.min_slope_x)
    assert res.gaussian.best_values["center"] == pytest.approx(5.0, abs=1e-2)
    assert res.com == pytest.approx(5.0, abs=1e-2)
    assert len(res.df.d1) == len(x)
    assert any("Fit (scan 1):" in call.args[0] for call in mock_echo.call_args_list)


def test_fit_scan_preferred_and_explicit_axes(
    session: BlueAPISession,
    gaussian_peak: tuple[list[float], list[float]],
) -> None:
    x, y = gaussian_peak
    session.data["10"] = {"other": [1.0] * len(x), "energy": x, "signal": y}

    session.set_fit_axes("energy", "signal")
    res_pref = session.fit_scan("10")
    assert res_pref.gaussian.best_values["center"] == pytest.approx(5.0, abs=1e-2)

    res_explicit = session.fit_scan("10", x="energy", y="signal")
    assert res_explicit.gaussian.best_values["center"] == pytest.approx(5.0, abs=1e-2)


def test_fit_scan_single_column_uses_point_numbers(
    session: BlueAPISession,
    gaussian_peak: tuple[list[float], list[float]],
) -> None:
    _, y = gaussian_peak
    session.data["2"] = {"det": y}

    res = session.fit_scan("2")
    assert isinstance(res, FitResult)
    assert res.gaussian.best_values["center"] == pytest.approx(11.0, abs=1e-1)


def test_fit_scan_empty_raises(session: BlueAPISession) -> None:
    session.data["empty"] = {}
    with pytest.raises(ValueError, match="Scan has no data"):
        session.fit_scan("empty")


def test_auto_analyse_stores_fit_and_updates_last_fit(
    session: BlueAPISession,
    callback,
    gaussian_peak: tuple[list[float], list[float]],
) -> None:
    assert session.last_fit == LastFit()

    callback(_start_event(scan_id=42, uid="uid42", task_id="task42"))

    xs, ys = gaussian_peak
    for i, (xv, yv) in enumerate(zip(xs, ys, strict=True), start=1):
        callback(
            _data_event({"motor": xv, "det": yv}, seq_num=i, time=i, task_id="task42")
        )

    callback(_stop_event(uid="uid42", time=100, task_id="task42"))

    assert isinstance(session.last_fit, LastFit)
    assert session.last_fit.centre == pytest.approx(5.0, abs=1e-2)
    assert session.last_fit.com == pytest.approx(5.0, abs=1e-2)
    assert session.last_fit.max_slope_x is not None
    assert session.last_fit.min_slope_x is not None

    scan_data = session.data["42"]
    assert "gaussian" in scan_data
    assert "d1" in scan_data
    assert "d2" in scan_data
    assert scan_data["centre"] == [pytest.approx(5.0, abs=1e-2)]
    assert scan_data["com"] == [pytest.approx(5.0, abs=1e-2)]
    assert "zero_crossing" in scan_data
    assert "max_slope_x" in scan_data
    assert "min_slope_x" in scan_data


def test_auto_analyse_disabled_skips_fit(session: BlueAPISession, callback) -> None:
    session.auto_analyse = False

    callback(_start_event(scan_id=43, uid="uid43", task_id="task43"))
    callback(_stop_event(uid="uid43", time=1, task_id="task43"))

    assert session.last_fit == LastFit()
    assert "gaussian" not in session.data["43"]
