from unittest.mock import MagicMock, patch

import pytest
from zhinst.core import ziDAQServer

from sm_bluesky.common.server import HF2Server


@pytest.fixture
def mock_daq():
    """Patches Serial and returns the class mock."""
    with patch(
        "sm_bluesky.common.server.zurich_lockin_amplifier.ziDAQServer", spec=True
    ) as mock_daq:
        yield mock_daq


@pytest.fixture
def mock_server(mock_daq: ziDAQServer):
    """Provides a fresh server instance with a mocked device for every test."""
    mock_server = HF2Server()
    mock_server.device = mock_daq
    return mock_server


def test_connect_hardware_success(
    mock_server: HF2Server, caplog: pytest.LogCaptureFixture
):
    mock_server._setup_scope = MagicMock()
    mock_server.connect_hardware()

    mock_server._setup_scope.assert_called_once()
    assert f"HF2 Data server connected at {mock_server.hf2_ip}" in caplog.text


def test_connect_hardware_failed(
    mock_server: HF2Server, caplog: pytest.LogCaptureFixture, mock_daq: MagicMock
):
    error_message = "Failed to Connect"
    mock_daq.side_effect = Exception(error_message)
    mock_server._send_error = MagicMock()
    mock_server.connect_hardware()
    mock_server._send_error.assert_called_once_with(
        f"HF2 Connection failed: {error_message}"
    )


def test_disconnect_hardware_failed(mock_server: HF2Server):
    with patch.object(mock_server, "device") as mock_device:
        error_message = "Failed to disconnect"
        mock_device.disconnect.side_effect = Exception(error_message)
        mock_server._send_error = MagicMock()
        mock_server.disconnect_hardware()
        mock_server._send_error.assert_called_once_with(
            f"Error during HF2 disconnect: {error_message}"
        )


def test_disconnect_hardware_failed_no_device(mock_server: HF2Server):
    mock_server.device = None
    mock_server._send_error = MagicMock()
    mock_server.disconnect_hardware()
    mock_server._send_error.assert_called_once_with(
        "Attempted to disconnect hardware that was not connected"
    )


def test_disconnect_hardware(mock_server: HF2Server):
    with patch.object(mock_server, "device") as mock_device:
        mock_device.disconnect = MagicMock()
        mock_server.disconnect_hardware()
        mock_device.disconnect.assert_called_once()
        assert mock_server.device is None
