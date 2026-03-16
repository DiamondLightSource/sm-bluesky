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

        assert server.connect_hardware() is False
        assert f"Failed to connect to hardware {error_message}" in caplog.text
