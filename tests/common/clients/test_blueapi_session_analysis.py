from unittest.mock import MagicMock, patch

import pytest
from blueapi.config import ApplicationConfig
from blueapi.core import DataEvent

from sm_bluesky.common.clients.blueapi_session import BlueAPISession, FitResult


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
def populated_session(session: BlueAPISession) -> BlueAPISession:
    x_data = [float(i) for i in range(1, 11)]
    y_data = [2.0, 5.0, 15.0, 45.0, 100.0, 45.0, 15.0, 5.0, 2.0, 1.0]
    session.data["scan_1"] = {
        "motor1": x_data,
        "det1": y_data,
    }
    session.current_scan_id = "scan_1"
    return session


def test_fit_scan_defaults_to_latest_scan_and_auto_resolves_channels(
    populated_session: BlueAPISession, mock_echo: MagicMock
) -> None:
    res = populated_session.fit_scan()

    assert isinstance(res, FitResult)
    assert res.gaussian.success is True
    assert res.gaussian.best_values["center"] == pytest.approx(5.0, abs=0.2)
    assert res.gaussian.params["height"] == pytest.approx(100.0, abs=10.0)
    assert res.com == pytest.approx(5.0, abs=0.2)
    assert res.df.zero_crossings == [pytest.approx(5.0, abs=0.2)]
    assert any(
        "Fit" in str(c) or "centre" in str(c) or "COM" in str(c)
        for c in mock_echo.call_args_list
    )


def test_fit_scan_explicit_scan_id_and_channels(
    populated_session: BlueAPISession,
) -> None:
    res = populated_session.fit_scan(scan_id="scan_1", x="motor1", y="det1")
    assert isinstance(res, FitResult)
    assert res.gaussian.best_values["center"] == pytest.approx(5.0, abs=0.2)


def test_fit_scan_with_user_guess(
    populated_session: BlueAPISession,
) -> None:
    guess = (90.0, 4.8, 1.0, 1.0)
    res = populated_session.fit_scan(scan_id="scan_1", guess=guess)
    assert isinstance(res, FitResult)
    assert isinstance(res, FitResult)
    assert res.gaussian.best_values["center"] == pytest.approx(5.0, abs=0.2)


def test_fit_scan_missing_scan_id_raises_or_warns(
    populated_session: BlueAPISession,
) -> None:
    with pytest.raises((ValueError, KeyError), match="non_existent_999"):
        populated_session.fit_scan(scan_id="non_existent_999")


@patch("IPython.start_ipython")
def test_start_shell_exports_analysis_utilities(
    mock_start: MagicMock, session: BlueAPISession
) -> None:
    session.start_shell()
    mock_start.assert_called_once()
    user_ns = mock_start.call_args.kwargs["user_ns"]

    assert "fit_scan" in user_ns
    assert user_ns["fit_scan"] == session.fit_scan


def test_auto_analyse_disabled_by_default(session: BlueAPISession) -> None:
    assert session.auto_analyse is True


def test_auto_analyse_triggers_on_scan_stop(
    session: BlueAPISession, mock_client_class: MagicMock, mock_echo: MagicMock
) -> None:
    """When auto_analyse is enabled, completing a scan triggers analysis."""
    session.auto_analyse = True
    callback = mock_client_class.from_config.return_value.add_callback.call_args[0][0]

    callback(
        DataEvent(
            name="start",
            doc={"scan_id": "auto_scan_1", "uid": "uid-1", "time": 0},
            task_id="task-1",
        )
    )

    x_vals = [float(i) for i in range(1, 10)]
    y_vals = [
        1.0,
        4.0,
        20.0,
        20.0,
        20.0,
        4.0,
        1.0,
        0.5,
        0.2,
    ]
    for pt, (x, y) in enumerate(zip(x_vals, y_vals, strict=False), start=1):
        callback(
            DataEvent(
                name="event",
                doc={"seq_num": pt, "data": {"motor": x, "detector": y}, "time": pt},
                task_id="task-1",
            )
        )
    callback(
        DataEvent(
            name="stop",
            doc={"exit_status": "success", "time": 10, "uid": "uid-1"},
            task_id="task-1",
        )
    )

    assert any(
        "Centre" in str(c) or "COM" in str(c) or "Fit" in str(c)
        for c in mock_echo.call_args_list
    )
    assert session.data["auto_scan_1"]["centre"][0] == pytest.approx(4.0, rel=0.01)
    assert session.data["auto_scan_1"]["com"][0] == pytest.approx(4.0, rel=0.01)
    assert session.data["auto_scan_1"]["zero_crossing"] == [4.0]
    assert session.data["auto_scan_1"]["max_slope_x"] == [2.0]
    assert session.data["auto_scan_1"]["min_slope_x"] == [6.0]
    assert len(session.data["auto_scan_1"]["fit"]) == len(x_vals)
    assert len(session.data["auto_scan_1"]["d1"]) == len(x_vals)
    assert len(session.data["auto_scan_1"]["d2"]) == len(x_vals)
