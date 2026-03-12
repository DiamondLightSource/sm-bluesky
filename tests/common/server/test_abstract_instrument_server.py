from unittest.mock import MagicMock, patch

import pytest

from sm_bluesky.common.server import AbstractInstrumentServer


class MockInstrument(AbstractInstrumentServer):
    def connect_hardware(self) -> None:
        self._hardwarde_connected = True

    def disconnect_hardware(self) -> None:
        self._hardwarde_connected = False

    def _handle_command(self, cmd: bytes, arg: bytes) -> None:
        if cmd == b"shutdown":
            self._send_response("Shutting down server")
            self.stop()
        if cmd == b"ping":
            self._send_ack()
        if cmd == "disconnect":
            self.disconnect_hardware()

        self._send_error("Unknown command")


@pytest.fixture
def mock_instrument():
    return MockInstrument(host="localhost", port=8888)


def test_connect_hardware(mock_instrument: AbstractInstrumentServer):
    assert mock_instrument.connect_hardware() is True


def test_start_server_success(
    mock_instrument: AbstractInstrumentServer, caplog: pytest.LogCaptureFixture
):
    mock_instrument.start()
    mock_instrument._run_command_loop = MagicMock()
    assert mock_instrument._is_running is True
    assert mock_instrument.connect_hardware() is True
    assert "Hardware connected successfully" in caplog.text
    assert (
        f"Server started on {mock_instrument.host}:{mock_instrument.port}"
        in caplog.text
    )
    assert mock_instrument._run_command_loop.assert_called_once()


def test_start_server_failure_hardware(
    mock_instrument: AbstractInstrumentServer, caplog: pytest.LogCaptureFixture
):
    # Simulate hardware connection failure by overriding the method
    mock_instrument.connect_hardware = MagicMock(
        side_effect=Exception("Simulated Hardware Failure")
    )
    pytest.raises(
        Exception, match="Simulated Hardware Failure", func=mock_instrument.start
    )
    assert mock_instrument._is_running is False


@patch(
    "sm_bluesky.common.server.abstract_instrument_server.AbstractInstrumentServer.socket.socket",
    autospec=True,
)
def test_start_server_failure_socket(
    mock_socket: MagicMock,
    mock_instrument: AbstractInstrumentServer,
    caplog: pytest.LogCaptureFixture,
):

    # Simulate socket failure by overriding the method
    mock_socket.side_effect = Exception("Simulated Socket Failure")
    mock_instrument.start()
    assert mock_instrument._is_running is False
    assert "Failed to start server" in caplog.text
    assert "Simulated Socket Failure" in caplog.text


def test_stop_server(
    mock_instrument: AbstractInstrumentServer, caplog: pytest.LogCaptureFixture
):
    mock_instrument._server_socket = MagicMock()
    mock_instrument.start()
    assert mock_instrument._is_running is True
    assert mock_instrument._server_socket is not None
    assert mock_instrument._hardwarde_connected is True
    mock_instrument._handle_command(b"shutdown", b"")
    assert mock_instrument._hardwarde_connected is False
    assert mock_instrument._is_running is False
    assert "Server stopped" in caplog.text


def test_send_ack(mock_instrument: AbstractInstrumentServer):
    mock_instrument._server_socket.sendall = MagicMock()
    mock_instrument._handle_command(b"ping", b"")
    assert mock_instrument._server_socket.sendall.assert_called_once_with(b"1\n")


def test_send_error(mock_instrument: AbstractInstrumentServer):
    mock_instrument._server_socket.sendall = MagicMock()
    mock_instrument._handle_command(b"unknown", b"")
    assert mock_instrument._server_socket.sendall.assert_called_once_with(
        b"0\tUnknown command\n"
    )


def test_send_response(mock_instrument: AbstractInstrumentServer):
    mock_instrument._server_socket.sendall = MagicMock()
    mock_instrument._handle_command(b"shutdown", b"")
    assert mock_instrument._server_socket.sendall.assert_called_once_with(
        b"1\tShutting down server\n"
    )
