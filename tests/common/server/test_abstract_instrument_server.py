from unittest.mock import MagicMock, patch

import pytest

from sm_bluesky.common.server import AbstractInstrumentServer


class MockInstrument(AbstractInstrumentServer):
    def connect_hardware(self) -> bool:
        self._hardware_connected = True
        return True

    def disconnect_hardware(self) -> None:
        self._hardware_connected = False

    def _handle_command(self, cmd: bytes, arg: bytes) -> None:
        if cmd == b"shutdown":
            self._send_response("Shutting down server")
            self.stop()
        if cmd == b"ping":
            self._send_ack()
        if cmd == b"disconnect":
            self.disconnect_hardware()

        self._send_error("Unknown command")


@pytest.fixture
def mock_instrument():
    return MockInstrument(host="localhost", port=8888)


def test_connect_hardware(mock_instrument: AbstractInstrumentServer):
    assert mock_instrument._hardware_connected is False
    mock_instrument.connect_hardware()
    assert mock_instrument._hardware_connected is True


@patch("socket.socket")
def test_start_server_success(
    mock_socket_class: MagicMock,
    mock_instrument: AbstractInstrumentServer,
    caplog: pytest.LogCaptureFixture,
):
    mock_server_socket = MagicMock()
    mock_socket_class.return_value = mock_server_socket
    mock_client_socket = MagicMock()
    mock_server_socket.accept.return_value = (mock_client_socket, ("localhost", 8888))

    mock_instrument._run_command_loop = lambda: setattr(
        mock_instrument, "_is_running", False
    )
    mock_instrument.start()

    mock_server_socket.bind.assert_called_with(("localhost", 8888))
    assert "Server started listening on localhost:8888" in caplog.text
    mock_server_socket.listen.assert_called_once()
    mock_server_socket.accept.assert_called_once()
    assert mock_instrument._is_running is False
    assert "Connection accepted from" in caplog.text


def test_start_server_failure_hardware(
    mock_instrument: AbstractInstrumentServer, caplog: pytest.LogCaptureFixture
):
    # Simulate hardware connection failure by overriding the method
    mock_instrument.connect_hardware = MagicMock(side_effect=[False])
    with pytest.raises(RuntimeError, match="Failed to connect hardware"):
        mock_instrument.start()
    assert "Failed to connect hardware" in caplog.text

    assert mock_instrument._is_running is False


@patch("socket.socket")
def test_start_server_failure_on_accept(
    mock_socket: MagicMock,
    mock_instrument: AbstractInstrumentServer,
    caplog: pytest.LogCaptureFixture,
):
    error_message = "Simulated socket error"
    mock_instance = MagicMock()
    mock_socket.return_value = mock_instance

    mock_instance.accept.side_effect = Exception(error_message)
    mock_instrument.start()

    assert mock_instrument._is_running is False
    assert f"Error in server loop: {error_message}" in caplog.text
    assert mock_instrument._conn is None


@patch("socket.socket", autospec=True)
def test_stop_server(
    mock_socket_class: MagicMock,
    mock_instrument: AbstractInstrumentServer,
    caplog: pytest.LogCaptureFixture,
):
    mock_server_socket = MagicMock()
    mock_socket_class.return_value = mock_server_socket
    mock_client_socket = MagicMock()
    mock_instrument._conn = mock_client_socket
    mock_server_socket.accept.return_value = (mock_client_socket, ("localhost", 8888))
    mock_instrument._conn.recv = MagicMock(return_value=b"shutdown\t")
    mock_instrument.start()
    # mock_instrument._handle_command(b"shutdown", b"")
    assert mock_instrument._hardware_connected is False
    assert mock_instrument._is_running is False
    assert "Server stopped" in caplog.text


@patch("socket.socket")
def test_send_ack(mock_instrument: AbstractInstrumentServer):
    mock_instrument._conn.sendall = MagicMock()
    mock_instrument._handle_command(b"ping", b"")
    mock_instrument._conn.sendall.assert_called_once_with(b"1\n")


def test_send_error(mock_instrument: AbstractInstrumentServer):
    mock_instrument._server_socket.sendall = MagicMock()
    mock_instrument._handle_command(b"unknown", b"")
    mock_instrument._server_socket.sendall.assert_called_once_with(
        b"0\tUnknown command\n"
    )


def test_send_response(mock_instrument: AbstractInstrumentServer):
    mock_instrument._server_socket.sendall = MagicMock()
    mock_instrument._handle_command(b"shutdown", b"")
    mock_instrument._server_socket.sendall.assert_called_once_with(
        b"1\tShutting down server\n"
    )
