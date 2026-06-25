from unittest.mock import MagicMock, patch

import pytest

from sm_bluesky.common.client import InstrumentClient


@pytest.fixture
def client():
    return InstrumentClient(host="127.0.0.1", port=8888, timeout=8.0)


@pytest.fixture
def mock_network():
    mock_socket = MagicMock()
    mock_reader = MagicMock()

    with (
        patch("socket.create_connection") as mock_connect,
        patch.object(mock_socket, "makefile") as mock_makefile,
    ):
        mock_connect.return_value.__enter__.return_value = mock_socket
        mock_makefile.return_value.__enter__.return_value = mock_reader
        yield {
            "connect": mock_connect,
            "socket": mock_socket,
            "reader": mock_reader,
        }


def test_send_payload_success(client, mock_network):
    mock_network["reader"].readline.return_value = "1\t512\n"
    result = client.send_payload("SET_DELAY", 512)
    assert result == "512"
    mock_network["connect"].assert_called_once_with(("127.0.0.1", 8888), timeout=8.0)
    mock_network["socket"].sendall.assert_called_once_with(b"SET_DELAY\t512\n")


def test_send_payload_server_error(client, mock_network):
    mock_network["reader"].readline.return_value = "0\tInvalid parameter boundary\n"

    with pytest.raises(
        ConnectionError,
        match="Communication layer failure: Server Error: Invalid parameter boundary",
    ):
        client.send_payload("SET_DELAY", -999)


def test_send_payload_network_failure(client, mock_network):
    mock_network["connect"].create_connection.return_value = TimeoutError(
        "Connection timed out"
    )
    with pytest.raises(ConnectionError, match="Communication layer failure"):
        client.send_payload("GET_STATUS")


def test_send_payload_empty_response(client, mock_network):
    mock_network["reader"].readline.return_value = ""

    with pytest.raises(
        ConnectionError, match="Server closed connection without returning data."
    ):
        client.send_payload("PING")
