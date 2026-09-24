from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from blueapi.config import ApplicationConfig
from blueapi.core import DataEvent

from sm_bluesky.common.clients.blueapi_session import BlueAPISession, load_config


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


@patch("sm_bluesky.common.clients.blueapi_session.BlueapiClient")
@patch("sm_bluesky.common.clients.blueapi_session.click.echo")
@patch("sm_bluesky.common.clients.blueapi_session.click.secho")
def test_blueapi_session_initialization_with_instrument_session(
    mock_secho: MagicMock, mock_echo: MagicMock, mock_client_class: MagicMock
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


@patch("sm_bluesky.common.clients.blueapi_session.BlueapiClient")
@patch("sm_bluesky.common.clients.blueapi_session.click.secho")
def test_blueapi_session_initialization_without_instrument_session(
    mock_secho: MagicMock, mock_client_class: MagicMock
) -> None:
    config = ApplicationConfig()

    BlueAPISession(config=config)

    mock_secho.assert_called_once_with(
        "\n[Notice] No instrument session set."
        " Set `bc.instrument_session = '<session_id>'` before dispatching plans.",
        fg="red",
    )


@patch("sm_bluesky.common.clients.blueapi_session.BlueapiClient")
@patch("IPython.embed")
def test_start_shell(mock_embed: MagicMock, mock_client_class: MagicMock) -> None:
    config = ApplicationConfig()
    session = BlueAPISession(config=config)
    session.start_shell()
    mock_embed.assert_called_once()
    kwargs = mock_embed.call_args.kwargs
    assert "bc" in kwargs["user_ns"]
    assert "pl" in kwargs["user_ns"]
    assert "dev" in kwargs["user_ns"]
    assert "scan_data" in kwargs["user_ns"]
    assert kwargs["user_ns"]["bc"] is session.bc


@patch("sm_bluesky.common.clients.blueapi_session.BlueapiClient")
@patch("sm_bluesky.common.clients.blueapi_session.click.echo")
def test_callbacks_handling(mock_echo: MagicMock, mock_client_class: MagicMock) -> None:
    config = ApplicationConfig()
    session = BlueAPISession(config=config)

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


def test_bc_property_not_initialized() -> None:
    session = BlueAPISession.__new__(BlueAPISession)
    session._bc = None
    with pytest.raises(RuntimeError, match="BlueAPI client is not initialized."):
        _ = session.bc


@patch("sm_bluesky.common.clients.blueapi_session.BlueapiClient")
@patch("sm_bluesky.common.clients.blueapi_session.click.echo")
def test_callback_event_without_scan_id(
    mock_echo: MagicMock, mock_client_class: MagicMock
) -> None:
    config = ApplicationConfig()
    session = BlueAPISession(config=config)

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
