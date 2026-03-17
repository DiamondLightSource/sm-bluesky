from unittest.mock import MagicMock, patch

import pytest
from serial import Serial

from sm_bluesky.common.server import pulse_generator_shanghai_tech


def test_connect_hardware_success():

    with patch(
        "sm_bluesky.common.server.pulse_generator_shanghai_tech.Serial"
    ) as mock_serial_class:
        mock_serial_class.return_value = MagicMock(spec=Serial)
        server = pulse_generator_shanghai_tech.GeneratorServerShanghaiTech(
            host="localhost", port=8888, usb_port="COM4", baud_rate=9600, timeout=1.0
        )
        assert server.connect_hardware() is True


def test_connect_hardware_failure(caplog: pytest.LogCaptureFixture):
    with patch(
        "sm_bluesky.common.server.pulse_generator_shanghai_tech.Serial"
    ) as mock_serial_class:
        error_message = "Connection failed"
        mock_serial_class.side_effect = Exception(error_message)
        server = pulse_generator_shanghai_tech.GeneratorServerShanghaiTech(
            host="localhost", port=8888, usb_port="COM4", baud_rate=9600, timeout=1.0
        )
        server._send_error = MagicMock()
        assert server.connect_hardware() is False
        assert f"Failed to connect to hardware {error_message}" in caplog.text
        server._send_error.assert_called_with(
            f"Failed to connect to hardware {error_message}"
        )


@patch("sm_bluesky.common.server.pulse_generator_shanghai_tech.Serial")
def test_disconnect_hardware(
    mock_serial_class: MagicMock, caplog: pytest.LogCaptureFixture
):
    mock_serial_class.side_effect = MagicMock(spec=Serial)
    server = pulse_generator_shanghai_tech.GeneratorServerShanghaiTech(
        host="localhost", port=8888, usb_port="COM4", baud_rate=9600, timeout=1.0
    )
    server.connect_hardware()
    with patch.object(server, "device") as mock_device:
        server._send_response = MagicMock()
        server.disconnect_hardware()
        mock_device.close.assert_called_once()
        assert server._hardware_connected is False
        assert server.device is None
        assert "Hardware disconnected successfully" in caplog.text
        server._send_response.assert_called_with("Hardware disconnected")


@patch("sm_bluesky.common.server.pulse_generator_shanghai_tech.Serial")
def test_disconnect_hardware_not_connected(
    mock_serial_class: MagicMock, caplog: pytest.LogCaptureFixture
):
    mock_serial_class.side_effect = MagicMock(spec=Serial)
    server = pulse_generator_shanghai_tech.GeneratorServerShanghaiTech(
        host="localhost", port=8888, usb_port="COM4", baud_rate=9600, timeout=1.0
    )
    server.connect_hardware()
    with patch.object(server, "device") as mock_device:
        mock_device.is_open = False
        server._send_error = MagicMock()
        server.disconnect_hardware()
        mock_device.close.assert_not_called()
        assert server._hardware_connected is False
        assert "Attempted to disconnect hardware that was not connected" in caplog.text
        server._send_error.assert_called_with(
            "Attempted to disconnect hardware that was not connected"
        )


@patch("sm_bluesky.common.server.pulse_generator_shanghai_tech.Serial")
def test_disconnect_hardware_exception_on_close(
    mock_serial_class: MagicMock, caplog: pytest.LogCaptureFixture
):
    mock_serial_class.side_effect = MagicMock(spec=Serial)
    server = pulse_generator_shanghai_tech.GeneratorServerShanghaiTech(
        host="localhost", port=8888, usb_port="COM4", baud_rate=9600, timeout=1.0
    )
    server.connect_hardware()
    with patch.object(server, "device") as mock_device:
        mock_device.close.side_effect = Exception("Close failed")
        server._send_error = MagicMock()
        server.disconnect_hardware()
        mock_device.close.assert_called_once()
        assert server._hardware_connected is False
        assert server.device is None
        assert "Error occurred while closing hardware connection" in caplog.text
        server._send_error.assert_called_with(
            "Error occurred while closing hardware connection Close failed"
        )
