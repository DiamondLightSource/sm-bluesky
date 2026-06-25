import socket
from time import sleep
from unittest.mock import MagicMock, patch

import pytest

from sm_bluesky.common.servers import AbstractInstrumentServer


class MockInstrument(AbstractInstrumentServer):
    def connect_hardware(self) -> bool:
        self._hardware_connected = True
        return True

    def disconnect_hardware(self) -> None:
        self._hardware_connected = False


@pytest.fixture
def mock_socket_instance():
    return MagicMock(spec=socket.socket)


@pytest.fixture
def mock_instrument(mock_socket_instance: MagicMock):

    with patch(
        "sm_bluesky.common.servers.abstract_instrument_server.socket.socket"
    ) as mock_socket_class:
        mock_socket_class.return_value = mock_socket_instance
        mock_instrument = MockInstrument(host="localhost", port=8888)
        yield mock_instrument


def test_connect_hardware(mock_instrument: AbstractInstrumentServer):
    assert mock_instrument._hardware_connected is False
    mock_instrument.connect_hardware()
    assert mock_instrument._hardware_connected is True


def test_start_server_success(
    mock_instrument: AbstractInstrumentServer,
    mock_socket_instance: MagicMock,
    caplog: pytest.LogCaptureFixture,
):
    mock_client_socket = MagicMock()
    mock_socket_instance.accept.return_value = (mock_client_socket, ("localhost", 8888))

    mock_instrument._serve_client = lambda: setattr(
        mock_instrument, "_is_running", False
    )
    mock_instrument.start()

    mock_socket_instance.bind.assert_called_with(("localhost", 8888))
    assert "Server started listening on localhost:8888" in caplog.text
    mock_socket_instance.listen.assert_called_once()
    mock_socket_instance.accept.assert_called_once()
    assert mock_instrument._is_running is False
    assert "Connection accepted from" in caplog.text


def test_start_handles_timeout(
    mock_instrument: AbstractInstrumentServer,
    mock_socket_instance: MagicMock,
):
    mock_socket_instance.accept.side_effect = [
        socket.timeout,
        (MagicMock(), ("8.8.8.8", 1234)),
    ]
    mock_instrument._serve_client = lambda: setattr(
        mock_instrument, "_is_running", False
    )
    mock_instrument.start()

    assert mock_socket_instance.accept.call_count == 2


def test_start_server_failure_hardware(
    mock_instrument: AbstractInstrumentServer, caplog: pytest.LogCaptureFixture
):
    # Simulate hardware connection failure by overriding the method
    mock_instrument.connect_hardware = MagicMock(side_effect=[False])
    with pytest.raises(RuntimeError, match="Failed to connect hardware"):
        mock_instrument.start()
    assert "Failed to connect hardware" in caplog.text

    assert mock_instrument._is_running is False


def test_start_server_failure_on_accept(
    mock_instrument: AbstractInstrumentServer,
    mock_socket_instance: MagicMock,
    caplog: pytest.LogCaptureFixture,
):
    error_message = "Simulated socket error"

    mock_socket_instance.accept.side_effect = Exception(error_message)
    mock_instrument.start()

    assert mock_instrument._is_running is False
    assert f"Error in server loop: {error_message}" in caplog.text
    assert mock_instrument._conn is None


def test_stop_server(
    mock_instrument: AbstractInstrumentServer,
    mock_socket_instance: MagicMock,
    caplog: pytest.LogCaptureFixture,
):

    mock_client_socket = MagicMock()
    mock_instrument._conn = mock_client_socket
    mock_socket_instance.accept.return_value = (mock_client_socket, ("localhost", 8888))
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
        b"0\tReceived unknown command: 'sdljkfnsdouifn': Unknown command\n"
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
    mock_instrument._send_response(b"data data data")
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


def test__timeout_context_timeout(mock_instrument: AbstractInstrumentServer):
    """Tests that a TimeoutError (hardware Watch trip) is caught and reported
    correctly."""

    cmd = b"getData"
    args = b"0.1"
    mock_handler = MagicMock(side_effect=TimeoutError("Hardware hung"))
    mock_instrument._command_registry[cmd] = mock_handler
    mock_instrument._error_helper = MagicMock()
    mock_instrument._handle_command(cmd, args)
    mock_instrument._error_helper.assert_called_once()
    args_called, _ = mock_instrument._error_helper.call_args
    assert "hardware not responding" in args_called[0].lower()
    assert isinstance(args_called[1], TimeoutError)


def test_check_timeout_raises_when_expired(mock_instrument: AbstractInstrumentServer):
    with mock_instrument._timeout_context(seconds=0.1):
        sleep(0.15)
        with pytest.raises(TimeoutError, match="Test Operation exceeded 0.1s limit"):
            mock_instrument._check_timeout("Test Operation")


def test_check_timeout_passes_when_valid(mock_instrument: AbstractInstrumentServer):
    """Verify that _check_timeout does nothing if time remains."""
    with mock_instrument._timeout_context(seconds=10):
        try:
            assert mock_instrument._current_deadline is not None
            mock_instrument._check_timeout("Quick Task")
        except TimeoutError:
            pytest.fail("TimeoutError raised unexpectedly")
    assert mock_instrument._current_deadline is None


def test_send_command_list(mock_instrument: AbstractInstrumentServer):
    """Verify that the command_list returns all registered commands."""
    mock_instrument._conn = MagicMock()
    mock_instrument._conn.sendall = MagicMock()
    mock_instrument._handle_command(b"command_list", b"")
    mock_instrument._conn.sendall.assert_called_once()
    called_bytes = mock_instrument._conn.sendall.call_args[0][0]

    assert called_bytes.startswith(b"1\t")
    assert called_bytes.endswith(b"\n")

    inner_payload = called_bytes[2:-1]
    commands = inner_payload.split(b"\t")

    assert b"ping" in commands
    assert b"connect_hardware" in commands
    assert b"disconnect_hardware" in commands
    assert b"shutdown" in commands
    assert b"command_list" in commands
