from unittest.mock import MagicMock, patch

import pytest
from blueapi.config import ApplicationConfig
from blueapi.core import DataEvent

from sm_bluesky.common.clients.blueapi_session import (
    BlueAPISession,
    FitResult,
    LastFit,
)


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
    initial_last_fit = populated_session.last_fit
    res = populated_session.fit_scan()

    assert isinstance(res, FitResult)
    assert res.gaussian.success is True
    assert res.gaussian.best_values["center"] == pytest.approx(5.0, abs=0.2)
    assert res.gaussian.params["height"] == pytest.approx(100.0, abs=10.0)
    assert res.com == pytest.approx(5.0, abs=0.2)
    assert res.df.zero_crossings == [pytest.approx(5.0, abs=0.2)]
    assert populated_session.last_fit is initial_last_fit
    assert populated_session.last_fit.centre == pytest.approx(5.0, abs=0.2)
    assert populated_session.last_fit.com == pytest.approx(5.0, abs=0.2)
    assert populated_session.last_fit.max_slope_x == pytest.approx(res.df.max_slope_x)
    assert populated_session.last_fit.min_slope_x == pytest.approx(res.df.min_slope_x)
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
    assert res.gaussian.best_values["center"] == pytest.approx(5.0, abs=0.2)


def test_fit_scan_missing_scan_id_raises_or_warns(
    populated_session: BlueAPISession,
) -> None:
    with pytest.raises((ValueError, KeyError), match="non_existent_999"):
        populated_session.fit_scan(scan_id="non_existent_999")


def test_fit_scan_with_set_fit_axes(session: BlueAPISession) -> None:
    x_data = [float(i) for i in range(1, 11)]
    y_wrong = [1.0] * 10
    y_peak = [2.0, 5.0, 15.0, 45.0, 100.0, 45.0, 15.0, 5.0, 2.0, 1.0]
    session.data["scan_multi"] = {
        "motor1": x_data,
        "det_noise": y_wrong,
        "det_roi": y_peak,
    }
    session.set_fit_axes(y="det_roi", log_df=True)
    assert session.log_df is True
    res = session.fit_scan(scan_id="scan_multi")
    assert res.gaussian.best_values["center"] == pytest.approx(5.0, abs=0.2)


def test_fit_scan_single_channel_falls_back_to_point_number(
    session: BlueAPISession,
) -> None:
    y_peak = [2.0, 5.0, 15.0, 45.0, 100.0, 45.0, 15.0, 5.0, 2.0, 1.0]
    session.data["scan_1ch"] = {"det1": y_peak}
    res = session.fit_scan(scan_id="scan_1ch")
    assert res.gaussian.best_values["center"] == pytest.approx(5.0, abs=0.2)


def test_fit_scan_empty_scan_raises(session: BlueAPISession) -> None:
    session.data["scan_empty"] = {}
    with pytest.raises(ValueError, match="Scan has no data"):
        session.fit_scan(scan_id="scan_empty")


def test_auto_analyse_enabled_by_default(session: BlueAPISession) -> None:
    assert session.auto_analyse is True
    assert session.last_fit == LastFit()


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
    assert len(session.data["auto_scan_1"]["gaussian"]) == len(x_vals)
    assert len(session.data["auto_scan_1"]["d1"]) == len(x_vals)
    assert len(session.data["auto_scan_1"]["d2"]) == len(x_vals)
    assert session.last_fit.centre == pytest.approx(4.0, rel=0.01)
    assert session.last_fit.com == pytest.approx(4.0, rel=0.01)
    assert session.last_fit.max_slope_x == pytest.approx(2.0)
    assert session.last_fit.min_slope_x == pytest.approx(6.0)

    callback(
        DataEvent(
            name="start",
            doc={"scan_id": "empty_scan", "uid": "uid-empty", "time": 11},
            task_id="task-empty",
        )
    )
    callback(
        DataEvent(
            name="stop",
            doc={"exit_status": "aborted", "time": 12, "uid": "uid-empty"},
            task_id="task-empty",
        )
    )
    mock_echo.assert_any_call("Auto-fit failed: Scan has no data")


def test_auto_analyse_disabled_skips_fit(
    session: BlueAPISession, mock_client_class: MagicMock
) -> None:
    session.auto_analyse = False
    callback = mock_client_class.from_config.return_value.add_callback.call_args[0][0]

    callback(
        DataEvent(
            name="start",
            doc={"scan_id": "auto_scan_off", "uid": "uid-2", "time": 0},
            task_id="task-2",
        )
    )
    callback(
        DataEvent(
            name="stop",
            doc={"exit_status": "success", "time": 1, "uid": "uid-2"},
            task_id="task-2",
        )
    )

    assert session.last_fit == LastFit()
    assert "gaussian" not in session.data["auto_scan_off"]
