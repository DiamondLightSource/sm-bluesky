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
    with patch.object(mock_server, "_device") as mock_device:
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
        "Error during HF2 disconnect: Lockin amplifier not connected"
    )


def test_disconnect_hardware(mock_server: HF2Server):
    with patch.object(mock_server, "_device") as mock_device:
        mock_device.disconnect = MagicMock()
        mock_server.disconnect_hardware()
        mock_device.disconnect.assert_called_once()
        assert mock_server._device is None


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
    with patch.object(mock_server, "_device") as mock_device:
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
    mock_server._device = MagicMock()
    mock_server._scope = MagicMock()
    mock_wave = np.array([1.0, 2.0, 3.0, 4.0])
    mock_result = {"/dev4206/scopes/0/wave": [[{"wave": [mock_wave]}]]}
    mock_server._scope.read.return_value = mock_result
    result = mock_server._get_single_scope_shot()
    assert result == 2.5

    expected_device_calls = [
        call.set("/dev4206/scopes/0/enable", 0),
        call.setInt("/dev4206/scopes/0/single", 1),
        call.setInt("/dev4206/scopes/0/enable", 1),
        call.sync(),
        call.set("/dev4206/scopes/0/enable", 0),
    ]
    mock_server._device.assert_has_calls(expected_device_calls, any_order=False)
    expected_scope_calls = [
        call.set("scopeModule/mode", 1),
        call.subscribe("/dev4206/scopes/0/wave/"),
        call.execute(),
        call.finish(),
        call.read(True),
        call.unsubscribe("*"),
    ]
    mock_server._scope.assert_has_calls(expected_scope_calls, any_order=False)
    assert 1.0 / 1000.0 + mock_server._minimum_scope_wait == pytest.approx(
        mock_sleep.call_args.args[0], rel=0.01
    )


def test_get_single_scope_shot_connection_error(mock_server: HF2Server):
    """Verifies that it raises ConnectionError if components are missing."""
    mock_server._device = None
    mock_server._scope_frequency = 1
    with pytest.raises(ConnectionError, match="Lockin amplifier not connected"):
        mock_server._get_single_scope_shot()


def test_get_single_scope_shot_scope_error(mock_server: HF2Server):
    """Verifies that it raises ConnectionError if components are missing."""
    mock_server._scope = None
    mock_server._scope_frequency = 1
    with pytest.raises(
        ConnectionError,
        match="Scope module not initialized. Run setupScope before using scope.",
    ):
        mock_server._get_single_scope_shot()


def test_get_single_scope_shot_frequncy_error(mock_server: HF2Server):
    """Verifies that it raises ConnectionError if components are missing."""
    with pytest.raises(
        ValueError,
        match="Scope frequency not set, use 'setupScope' before taking data.",
    ):
        mock_server._get_single_scope_shot()


@patch("sm_bluesky.common.server.zurich_lockin_amplifier.time")
@patch("sm_bluesky.common.server.zurich_lockin_amplifier.sleep")
def test_get_lockin_data_averaging(
    mock_sleep: MagicMock, mock_time: MagicMock, mock_server: HF2Server
):
    mock_server._device = MagicMock()
    mock_time.side_effect = [100, 100.2, 100.4, 100.7, 100.8, 100.9, 102]
    mock_server._device.getSample.side_effect = [
        {"x": 1.0, "y": 2.0},
        {"x": 3.0, "y": 4.0},
    ]

    x, y, r, theta = mock_server._get_lockin_data(1.0)

    assert x == 2.0
    assert y == 3.0
    assert r == pytest.approx(3.60555, rel=1e-4)

    assert theta == pytest.approx(56.3099, rel=1e-4)
    mock_sleep.assert_called_with(0.01)
    assert mock_server._device.getSample.call_count == 2


def test_get_lockin_data_fail(mock_server: HF2Server):
    mock_server.device = None
    with pytest.raises(ConnectionError, match="Lockin amplifier not connected"):
        mock_server._get_lockin_data(0.1)


@pytest.mark.parametrize(
    "method_name, val_bytes, expected_path, expected_val, expected_response",
    [
        (
            "_set_time_constant",
            b"0.01",
            "/dev4206/demods/0/timeconstant",
            0.01,
            b"Time constant set",
        ),
        ("_set_data_rate", b"400", "/dev4206/demods/0/rate", 400.0, b"Data rate set"),
        (
            "_set_ref_vpk",
            b"0.5",
            "/dev4206/sigouts/0/amplitudes/1",
            0.5,
            b"Ref Vpk set",
        ),
        ("_set_ref_voff", b"0.1", "/dev4206/sigouts/0/offset", 0.1, b"Ref Voff set"),
        (
            "_set_ref_harmonic",
            b"2.0",
            "/dev4206/demods/1/harmonic",
            2.0,
            b"Harmonic set",
        ),
        ("_set_ref_freq", b"20.5", "/dev4206/oscs/0/freq", 20.5, b"Frequency set"),
        (
            "_set_current_range",
            b"1e-4",
            "/dev4206/currins/0/range",
            10.0**-4,
            b"Current range set",
        ),
    ],
)
def test_commond_mapping_method_double(
    mock_server: HF2Server,
    method_name: str,
    val_bytes: bytes,
    expected_path: str,
    expected_val: float,
    expected_response: bytes,
):
    method = getattr(mock_server, method_name)
    mock_server._device = MagicMock()
    mock_server._send_response = MagicMock()
    method(val_bytes)
    mock_server._device.setDouble.assert_called_once_with(expected_path, expected_val)
    response = expected_response + b": %f" % expected_val
    mock_server._send_response.assert_called_once_with(response)


@pytest.mark.parametrize(
    "method_name, val_bytes, expected_path, expected_response",
    [
        (
            "_auto_voltage_range",
            [],
            "/dev4206/sigins/0/autorange",
            b"Auto voltage triggered",
        ),
        (
            "_auto_current_range",
            [],
            "/dev4206/currins/0/autorange",
            b"Auto current triggered",
        ),
        (
            "_set_ref_output",
            [b"1"],
            "/dev4206/sigouts/0/enables/1",
            b"Output set to",
        ),
    ],
)
def test_commond_mapping_method_int(
    mock_server: HF2Server,
    method_name: str,
    val_bytes: bytes,
    expected_path: str,
    expected_response: bytes,
):
    method = getattr(mock_server, method_name)
    mock_server._send_response = MagicMock()
    mock_server._device = MagicMock()
    method(*val_bytes)

    mock_server._device.setInt.assert_called_once_with(expected_path, 1)
    mock_server._send_response.assert_called_once_with(expected_response + b": 1")


def test_get_combined_data(
    mock_server: HF2Server,
):
    duration = b"0.2"
    mock_server._get_lockin_data = MagicMock(return_value={1, 2, 3, 4})
    mock_server._get_single_scope_shot = MagicMock(return_value=5)
    mock_server._send_response = MagicMock()
    mock_server._get_combined_data(duration)  # type: ignore
    mock_server._get_lockin_data.assert_called_once_with(
        float(duration.decode("utf-8"))
    )
    mock_server._get_single_scope_shot.assert_called_once()
    response = f"{1:e}, {2:e}, {4:f}, {5:e}, {3:e}".encode()
    mock_server._send_response.assert_called_once_with(response)


def test_setup_scope_cmd(mock_server: HF2Server):
    mock_server._setup_scope = MagicMock()
    mock_server._send_response = MagicMock()
    mock_server._setup_scope_cmd()
    assert mock_server._send_response(b"Scope configured")
    mock_server._setup_scope.assert_called_once()
