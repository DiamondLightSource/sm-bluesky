from unittest.mock import MagicMock, patch

import pytest
from blueapi.config import ApplicationConfig

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
    """Session populated with a synthetic 1D scan containing a clear peak."""
    x_data = [float(i) for i in range(1, 11)]
    y_data = [2.0, 5.0, 15.0, 45.0, 100.0, 45.0, 15.0, 5.0, 2.0, 1.0]
    session.data["scan_1"] = {
        "Point number": list(range(1, 11)),
        "motor1": x_data,
        "det1": y_data,
    }
    session.current_scan_id = "scan_1"
    return session


def test_fit_scan_defaults_to_latest_scan_and_auto_resolves_channels(
    populated_session: BlueAPISession, mock_echo: MagicMock
) -> None:
    """Calling fit_scan() without args fits latest scan and prints results."""
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
    """User can pass an initial guess tuple or dict to fit_scan()."""
    guess = (90.0, 4.8, 1.0, 1.0)
    res = populated_session.fit_scan(scan_id="scan_1", guess=guess)
    assert isinstance(res, FitResult)
    assert isinstance(res, FitResult)
    assert res.gaussian.best_values["center"] == pytest.approx(5.0, abs=0.2)


def test_fit_scan_missing_scan_id_raises_or_warns(
    populated_session: BlueAPISession,
) -> None:
    """Attempting to fit a non-existent scan ID handles cleanly."""
    with pytest.raises((ValueError, KeyError), match="non_existent_999"):
        populated_session.fit_scan(scan_id="non_existent_999")


@patch("IPython.start_ipython")
def test_start_shell_exports_analysis_utilities(
    mock_start: MagicMock, session: BlueAPISession
) -> None:
    """IPython shell must expose analysis utilities in user_ns."""
    session.start_shell()
    mock_start.assert_called_once()
    user_ns = mock_start.call_args.kwargs["user_ns"]

    assert "fit_scan" in user_ns
    assert user_ns["fit_scan"] == session.fit_scan
