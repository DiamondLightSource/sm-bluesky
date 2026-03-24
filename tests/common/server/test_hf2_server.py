from unittest.mock import MagicMock, call, patch

import numpy as np
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


@pytest.mark.parametrize(
    "args, expected",
    [
        ([10], [10, 4096, 0, 0]),
        ([10, 11], [10, 11, 0, 0]),
        ([10, 11, 322], [10, 11, 322, 0]),
    ],
)
def test_setup_scope_success(args: list[int], expected: list, mock_server: HF2Server):
    cmd = ["time", "length", "channels/0/inputselect", "enable"]
    with patch.object(mock_server, "device") as mock_device:
        mock_device.set = MagicMock()
        mock_server._setup_scope(*args)
        for i, arg in enumerate(mock_device.set.call_args_list):
            assert arg.args == (
                f"/{mock_server.device_id}/scopes/0/{cmd[i]}",
                expected[i],
            )


def test_setup_scope_failed_no_device(mock_server: HF2Server):
    mock_server.device = None
    mock_server._send_error = MagicMock()
    with pytest.raises(ConnectionError, match="Lockin amplifier not connected"):
        mock_server._setup_scope()


@patch("sm_bluesky.common.server.zurich_lockin_amplifier.sleep")
def test_get_single_scope_shot_success(mock_sleep: MagicMock, mock_server: HF2Server):

    mock_server._scope_frequency = 1000
    mock_server.device = MagicMock()
    mock_server.scope = MagicMock()
    mock_wave = np.array([1.0, 2.0, 3.0, 4.0])
    mock_result = {"/dev4206/scopes/0/wave": [[{"wave": [mock_wave]}]]}
    mock_server.scope.read.return_value = mock_result
    result = mock_server._get_single_scope_shot()
    assert result == 2.5

    expected_device_calls = [
        call.__bool__(),
        call.set("/dev4206/scopes/0/enable", 0),
        call.setInt("/dev4206/scopes/0/single", 1),
        call.setInt("/dev4206/scopes/0/enable", 1),
        call.sync(),
        call.set("/dev4206/scopes/0/enable", 0),
    ]
    mock_server.device.assert_has_calls(expected_device_calls, any_order=False)
    expected_scope_calls = [
        call.__bool__(),
        call.set("scopeModule/mode", 1),
        call.subscribe("/dev4206/scopes/0/wave/"),
        call.execute(),
        call.finish(),
        call.read(True),
        call.unsubscribe("*"),
    ]
    mock_server.scope.assert_has_calls(expected_scope_calls, any_order=False)
    assert 1.0 / 1000.0 + mock_server._minimum_scope_wait == pytest.approx(
        mock_sleep.call_args.args[0], rel=0.01
    )


def test_get_single_scope_shot_connection_error(mock_server: HF2Server):
    """Verifies that it raises ConnectionError if components are missing."""
    mock_server.device = None  # Simulate disconnected state

    with pytest.raises(ConnectionError, match="Lockin amplifier not connected"):
        mock_server._get_single_scope_shot()
