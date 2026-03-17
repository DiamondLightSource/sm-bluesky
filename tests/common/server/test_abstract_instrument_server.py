import socket
from unittest.mock import MagicMock, patch

import pytest

from sm_bluesky.common.server import AbstractInstrumentServer


class MockInstrument(AbstractInstrumentServer):
    def connect_hardware(self) -> bool:
        self._hardware_connected = True
        return True

    def disconnect_hardware(self) -> None:
        self._hardware_connected = False


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

    mock_instrument._serve_client = lambda: setattr(
        mock_instrument, "_is_running", False
    )
    mock_instrument.start()

    mock_server_socket.bind.assert_called_with(("localhost", 8888))
    assert "Server started listening on localhost:8888" in caplog.text
    mock_server_socket.listen.assert_called_once()
    mock_server_socket.accept.assert_called_once()
    assert mock_instrument._is_running is False
    assert "Connection accepted from" in caplog.text


@patch("socket.socket")
def test_start_handles_timeout(mock_socket_class, mock_instrument):
    mock_instance = MagicMock()
    mock_socket_class.return_value = mock_instance
    mock_instance.accept.side_effect = [
        socket.timeout,
        (MagicMock(), ("8.8.8.8", 1234)),
    ]

    with patch.object(
        mock_instrument,
        "_serve_client",
        side_effect=lambda: setattr(mock_instrument, "_is_running", False),
    ):
        mock_instrument.start()

    assert mock_instance.accept.call_count == 2


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


@patch("socket.socket")
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
    mock_instrument._conn.recv = MagicMock(return_value=b"shutdown\t\n")
    mock_instrument.start()
    assert mock_instrument._hardware_connected is False
    assert mock_instrument._is_running is False
    assert "Server stopped" in caplog.text


def test_send_ack(mock_instrument: AbstractInstrumentServer):
    mock_instrument._conn = MagicMock()
    mock_instrument._conn.sendall = MagicMock()
    mock_instrument._handle_command(b"ping", b"")
    mock_instrument._conn.sendall.assert_called_once_with(b"1\t\n")


def test_send_unknow_command_error(mock_instrument: AbstractInstrumentServer):
    mock_instrument._conn = MagicMock()
    mock_instrument._conn.sendall = MagicMock()
    mock_instrument._handle_command(b"sdljkfnsdouifn", b"")
    mock_instrument._conn.sendall.assert_called_once_with(
        b"0\tReceived unknown command: 'sdljkfnsdouifn': Unknow command\n"
    )


def test_send_command_handling_error(mock_instrument: AbstractInstrumentServer):
    mock_instrument._conn = MagicMock()
    mock_instrument._conn.sendall = MagicMock()

    def handling_exception():
        raise Exception(Exception("test_send_command_handling_error"))

    mock_instrument._command_registry.update({b"ping": handling_exception})
    mock_instrument._handle_command(b"ping", b"")
    mock_instrument._conn.sendall.assert_called_once_with(
        b"0\tError handling command 'ping': test_send_command_handling_error\n"
    )


def test_send_response(mock_instrument: AbstractInstrumentServer):
    mock_instrument._conn = MagicMock()
    mock_instrument._conn.sendall = MagicMock()
    mock_instrument._send_response("data data data")
    mock_instrument._conn.sendall.assert_called_once_with(b"1\tdata data data\n")


def test_serve_client_eof(
    mock_instrument: AbstractInstrumentServer,
):
    mock_conn = MagicMock()
    mock_instrument._conn = mock_conn
    mock_conn.recv.side_effect = [b"", b"shutdown\t\n"]
    mock_instrument._is_running = True
    mock_instrument._serve_client()
    mock_instrument._conn.recv.assert_called_once()


def test_serve_client_no_client_connected(
    mock_instrument: AbstractInstrumentServer,
    caplog: pytest.LogCaptureFixture,
):
    mock_instrument._conn = None
    mock_instrument._serve_client()
    assert "No client connection available to run command loop" in caplog.text


def test_serve_client_exception(
    mock_instrument: AbstractInstrumentServer,
    caplog: pytest.LogCaptureFixture,
):
    mock_conn = MagicMock()
    mock_instrument._conn = mock_conn
    mock_conn.recv.side_effect = [
        OSError("Simulated connection error"),
        b"shutdown\t\n",
    ]
    mock_instrument._is_running = True
    mock_instrument._serve_client()
    mock_instrument._conn.recv.assert_called_once()
    assert "Client connection lost unexpectedly" in caplog.text


def test_full_connection_cycle_cleanup(mock_instrument, caplog):
    mock_instance = MagicMock()
    mock_instance.accept.return_value = (MagicMock(), ("8.8.8.8", 1234))
    mock_instrument._server_socket = mock_instance

    with patch.object(mock_instrument, "_serve_client", side_effect=None):
        client_info = (MagicMock(), "8.8.8.8")
        with mock_instrument._manage_connection(client_info):
            pass
    client_info[0].close.assert_called_once()
    assert mock_instrument._conn is None
    assert "Client disconnected" in caplog.text


def test_dispatch_command_exception_handling(
    mock_instrument: AbstractInstrumentServer, caplog: pytest.LogCaptureFixture
):
    mock_instrument._handle_command = MagicMock(side_effect=Exception("Test exception"))
    mock_instrument._send_error = MagicMock()
    mock_instrument._dispatch_command(b"test exception")
    mock_instrument._send_error.assert_called_once_with("Handler Error: Test exception")


def test_dispatch_command_with_arg(mock_instrument: AbstractInstrumentServer):
    mock_instrument._handle_command = MagicMock()
    mock_instrument._dispatch_command(b"command\targument\targument2")
    mock_instrument._handle_command.assert_called_once_with(
        b"command", b"argument\targument2"
    )
