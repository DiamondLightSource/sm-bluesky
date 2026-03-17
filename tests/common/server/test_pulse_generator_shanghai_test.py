from unittest.mock import MagicMock, patch

import pytest

from sm_bluesky.common.server import GeneratorServerShanghaiTech


@pytest.fixture
def mock_serial():
    """Patches Serial and returns the class mock."""
    with patch(
        "sm_bluesky.common.server.pulse_generator_shanghai_tech.Serial", spec=True
    ) as mock_serial:
        # Ensure calling Serial() returns a Mock instance with Serial methods
        # mock_serial.return_value = MagicMock(spec=Serial)
        yield mock_serial


@pytest.fixture
def mock_server(mock_serial):
    """Provides a fresh server instance with a mocked device for every test."""
    mock_server = GeneratorServerShanghaiTech(
        host="localhost", port=8888, usb_port="COM4", baud_rate=9600, timeout=1.0
    )
    return mock_server


def test_connect_hardware_success(mock_server: GeneratorServerShanghaiTech):
    assert mock_server.connect_hardware() is True


def test_connect_hardware_failure(
    mock_server: GeneratorServerShanghaiTech, caplog: pytest.LogCaptureFixture
):
    with patch(
        "sm_bluesky.common.server.pulse_generator_shanghai_tech.Serial"
    ) as mock_serial_class:
        error_message = "Connection failed"
        mock_serial_class.side_effect = Exception(error_message)
        mock_server._send_error = MagicMock()
        assert mock_server.connect_hardware() is False
        assert f"Failed to connect to hardware {error_message}" in caplog.text
        mock_server._send_error.assert_called_with(
            f"Failed to connect to hardware {error_message}"
        )


def test_disconnect_hardware(
    mock_server: GeneratorServerShanghaiTech, caplog: pytest.LogCaptureFixture
):
    mock_server.connect_hardware()
    with patch.object(mock_server, "device") as mock_device:
        mock_server._send_response = MagicMock()
        mock_server.disconnect_hardware()
        mock_device.close.assert_called_once()
        assert mock_server._hardware_connected is False
        assert mock_server.device is None
        assert "Hardware disconnected successfully" in caplog.text
        mock_server._send_response.assert_called_with("Hardware disconnected")


def test_disconnect_hardware_not_connected(
    mock_server: GeneratorServerShanghaiTech, caplog: pytest.LogCaptureFixture
):

    mock_server.connect_hardware()
    with patch.object(mock_server, "device") as mock_device:
        mock_device.is_open = False
        mock_server._send_error = MagicMock()
        mock_server.disconnect_hardware()
        mock_device.close.assert_not_called()
        assert mock_server._hardware_connected is False
        assert "Attempted to disconnect hardware that was not connected" in caplog.text
        mock_server._send_error.assert_called_with(
            "Attempted to disconnect hardware that was not connected"
        )


def test_disconnect_hardware_exception_on_close(
    mock_server: GeneratorServerShanghaiTech, caplog: pytest.LogCaptureFixture
):
    mock_server.connect_hardware()
    with patch.object(mock_server, "device") as mock_device:
        mock_device.close.side_effect = Exception("Close failed")
        mock_server._send_error = MagicMock()
        mock_server.disconnect_hardware()
        mock_device.close.assert_called_once()
        assert mock_server._hardware_connected is False
        assert mock_server.device is None
        assert "Error occurred while closing hardware connection" in caplog.text
        mock_server._send_error.assert_called_with(
            "Error occurred while closing hardware connection Close failed"
        )


def test_set_delay_success(
    mock_server: GeneratorServerShanghaiTech,
) -> None:
    mock_respond = "set success: 500"
    with patch.object(mock_server, "device") as mock_device:
        mock_device.readline.return_value = mock_respond.encode()
        mock_server._send_response = MagicMock()
        mock_server._set_delay(b"500")
        mock_server._send_response.assert_called_once_with(mock_respond)
        mock_device.readline.assert_called_once()
