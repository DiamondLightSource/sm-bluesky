from unittest.mock import MagicMock, patch

import pytest
from serial import Serial

from sm_bluesky.common.server import GeneratorServerShanghaiTech


@pytest.fixture
def mock_serial():
    """Patches Serial and returns the class mock."""
    with patch(
        "sm_bluesky.common.server.pulse_generator_shanghai_tech.Serial", spec=True
    ) as mock_serial:
        yield mock_serial


@pytest.fixture
def mock_server(mock_serial: Serial):
    """Provides a fresh server instance with a mocked device for every test."""
    mock_server = GeneratorServerShanghaiTech(
        host="localhost", port=8888, usb_port="COM4", baud_rate=9600, timeout=1.0
    )
    mock_server.device = mock_serial
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
        assert f"Failed to connect to hardware: {error_message}" in caplog.text
        mock_server._send_error.assert_called_with(
            f"Failed to connect to hardware: {error_message}"
        )


def test_disconnect_hardware(
    mock_server: GeneratorServerShanghaiTech, caplog: pytest.LogCaptureFixture
):

    with patch.object(mock_server, "device") as mock_device:
        mock_server._send_response = MagicMock()
        mock_server.disconnect_hardware()
        mock_device.close.assert_called_once()
        assert mock_server._hardware_connected is False
        assert "Hardware disconnected successfully" in caplog.text
        mock_server._send_response.assert_called_with(b"Hardware disconnected")


def test_disconnect_hardware_not_connected(
    mock_server: GeneratorServerShanghaiTech, caplog: pytest.LogCaptureFixture
):
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
    with patch.object(mock_server, "device") as mock_device:
        mock_device.close.side_effect = Exception("Close failed")
        mock_server._send_error = MagicMock()
        mock_server.disconnect_hardware()
        mock_device.close.assert_called_once()
        assert mock_server._hardware_connected is False
        assert "Error occurred while closing hardware connection" in caplog.text
        mock_server._send_error.assert_called_with(
            "Error occurred while closing hardware connection Close failed"
        )


def test_set_delay_success(
    mock_server: GeneratorServerShanghaiTech,
) -> None:
    mock_respond = b"set success: 500"
    with patch.object(mock_server, "device") as mock_device:
        mock_device.readline.return_value = mock_respond
        mock_server._send_response = MagicMock()
        mock_server._set_delay(b"500")
        mock_server._send_response.assert_called_once_with(mock_respond)
        mock_device.readline.assert_called_once()


def test_set_delay_failed(mock_server: GeneratorServerShanghaiTech) -> None:
    with patch.object(mock_server, "device") as mock_device:
        mock_device.write.side_effect = Exception("Write_failed")
        mock_server._send_error = MagicMock()
        mock_server._set_delay(b"112")
        mock_server._send_error.assert_called_once_with(
            "Set delay failed: Write_failed"
        )


@pytest.mark.parametrize("delay", [b"-200", b"1024", b"-1"])
def test_set_delay_failed_out_of_bound(
    delay: bytes,
    mock_server: GeneratorServerShanghaiTech,
) -> None:

    mock_server._send_error = MagicMock()
    mock_server._set_delay(delay)
    mock_server._send_error.assert_called_once_with(
        f"Set delay failed: Delay {delay.decode('utf-8')}"
        + f" is out of bounds (0-{mock_server.max_pulse_delay - 1})"
    )


def test_get_delay_success(mock_server: GeneratorServerShanghaiTech) -> None:
    test_reading = b"Test reading"
    with patch.object(mock_server, "device") as mock_device:
        mock_device.readline.return_value = test_reading
        mock_server._send_response = MagicMock()
        mock_server._get_delay()
    mock_device.write.assert_called_once_with(b"AT+DLSET=?\r\n")
    mock_server._send_response.assert_called_once_with(test_reading)


def test_get_delay_failed(mock_server: GeneratorServerShanghaiTech) -> None:
    with patch.object(mock_server, "device") as mock_device:
        mock_device.write.side_effect = Exception("Read_failed")
        mock_server._send_error = MagicMock()
        mock_server._get_delay()
        mock_server._send_error.assert_called_once_with(
            "Read delay failed: Read_failed"
        )


def test_reset_serial_buffer_success(mock_server: GeneratorServerShanghaiTech):
    with patch.object(mock_server, "device", spec=Serial) as mock_device:
        mock_server.device = mock_device
        mock_server._reset_serial_buffer()
        mock_server.device.reset_output_buffer.assert_called_once()
        mock_server.device.reset_input_buffer.assert_called_once()


def test_reset_serial_buffer_fail(mock_server: GeneratorServerShanghaiTech):
    with patch.object(mock_server, "device", spec=Serial) as mock_device:
        mock_server.device = mock_device
        mock_server.device.reset_output_buffer.side_effect = Exception(
            "Buffer reset failed"
        )
        mock_server._send_error = MagicMock()
        mock_server._reset_serial_buffer()
        mock_server._send_error.assert_called_once_with(
            "Buffer reset failed: Buffer reset failed"
        )


def test_passthrough_success(mock_server: GeneratorServerShanghaiTech):
    command = b"some commands"
    multi_line_responds = b"somethn\r\nsomethingelse\r\nmore\t\r\n"
    with patch.object(mock_server, "device", spec=Serial) as mock_device:
        mock_server._send_response = MagicMock()
        mock_server.device = mock_device
        mock_server.device.readline.return_value = multi_line_responds
        mock_server._passthrough(command)
        mock_server.device.write.assert_called_once_with(command + b"\r\n")
        mock_server._send_response.assert_called_once_with(multi_line_responds)


def test_passthrough_failed(mock_server: GeneratorServerShanghaiTech):
    with patch.object(mock_server, "device", spec=Serial) as mock_device:
        mock_server.device = mock_device
        mock_server.device.write.side_effect = Exception("Command pass through failed")
        mock_server._send_error = MagicMock()
        mock_server._passthrough(b"does not matter")
        mock_server._send_error.assert_called_once_with(
            "Command pass through failed: Command pass through failed"
        )
