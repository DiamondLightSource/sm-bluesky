import signal
import socket
from abc import ABC, abstractmethod
from collections.abc import Callable
from contextlib import contextmanager

from sm_bluesky.log import LOGGER, logging


class AbstractInstrumentServer(ABC):
    """
    Base class for TCP instrument servers.

    Handles socket lifecycle, connection management, and buffered command
    parsing. Subclasses must implement hardware-specific control logic.
    """

    def __init__(self, host: str, port: int, ipv6: bool = False):
        self.host: str = host
        self.port: int = port
        self._is_running: bool = False
        self._hardware_connected: bool = False
        self._server_socket: socket.socket
        self._conn: socket.socket | None = None
        self.address_type = socket.AF_INET6 if ipv6 else socket.AF_INET
        self._command_registry: dict[bytes, Callable] = {
            b"connect_hardware": self.connect_hardware,
            b"disconnect_hardware": self.disconnect_hardware,
            b"ping": self._send_ack,
            b"shutdown": self.stop,
        }

    def start(self) -> None:
        """Initializes the server, connects hardware, and enters the listening loop."""
        self._is_running = True

        self._hardware_connected = self.connect_hardware()
        if not self._hardware_connected:
            self._is_running = False
            LOGGER.error("Failed to connect hardware")
            raise RuntimeError("Failed to connect hardware")
        LOGGER.info("Hardware connected successfully")
        self._server_socket = socket.socket(self.address_type, socket.SOCK_STREAM)
        self._server_socket.bind((self.host, self.port))
        self._server_socket.listen()
        self._server_socket.settimeout(1.0)
        self._is_running = True

        LOGGER.info(f"Server started listening on {self.host}:{self.port}")

        while self._is_running:
            try:
                client_info = self._server_socket.accept()
                LOGGER.info(f"Connection accepted from {client_info}")
                with self._manage_connection(client_info):
                    self._serve_client()
            except socket.timeout:  # noqa: UP041
                continue
            except Exception as e:
                LOGGER.error(f"Error in server loop: {e}")
                self._is_running = False

    @contextmanager
    def _manage_connection(self, client_info: tuple[socket.socket, str]):
        """Manages the lifecycle of a client connection with automatic cleanup."""
        self._conn, addr = client_info
        LOGGER.info(f"Client {addr} connected. Server busy.")
        try:
            yield
        finally:
            self._disconnect_client()
            LOGGER.info(f"Client {addr} disconnected. Server ready.")

    @contextmanager
    def _hardware_watch(self, seconds: int = 60):
        """Context manager to interrupt hardware calls that took too long."""

        def handler(signum, frame):
            raise TimeoutError(f"Hardware call timed out after {seconds}s")

        signal.signal(signal.SIGALRM, handler)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)

    def stop(self) -> None:
        """Stops the server, closes sockets, and disconnects hardware."""
        self._disconnect_client()
        if hasattr(self, "_server_socket"):
            self._server_socket.close()
        if self._hardware_connected:
            self.disconnect_hardware()
            self._hardware_connected = False
        self._is_running = False
        LOGGER.info("Server stopped successfully")

    def _disconnect_client(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
            LOGGER.info("Client disconnected")

    def _serve_client(self) -> None:
        """Reads stream data from the client and handles command buffering."""
        if self._conn is None:
            LOGGER.error("No client connection available to run command loop")
            return
        buffer = b""
        while self._is_running:
            try:
                chunk = self._conn.recv(1024)
                if not chunk:
                    break
                buffer += chunk

                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if line:
                        self._dispatch_command(line.strip())

            except (OSError, ConnectionResetError):
                LOGGER.error("Client connection lost unexpectedly")
                break

    def _dispatch_command(self, line: bytes) -> None:
        """Parses raw input into command/argument pairs and executes the handler."""
        if b"\t" in line:
            cmd, arg = line.split(b"\t", 1)
        else:
            cmd, arg = line, b""

        try:
            self._handle_command(cmd, arg)
        except Exception as e:
            self._error_helper(message="Handler Error", error=e)

    def _send_ack(self) -> None:
        self._send_response()

    def _send_error(self, error_message: str) -> None:
        if self._conn:
            self._conn.sendall(b"0\t" + error_message.encode() + b"\n")

    def _send_response(self, response: bytes = b"") -> None:
        if self._conn:
            self._conn.sendall(b"1\t" + response + b"\n")

    def _handle_command(self, cmd: bytes, args: bytes) -> None:
        """Executes logic for a specific instrument command."""
        handler = self._command_registry.get(cmd)
        if not handler:
            self._error_helper(
                message=f"Received unknown command: '{cmd.decode()}'",
                error=Exception("Unknow command"),
                level=logging.WARNING,
            )
        else:
            try:
                with self._hardware_watch(seconds=60):
                    arg_list = args.split(b"\t") if args else []
                    handler(*arg_list)

            except TimeoutError as te:
                self._error_helper(
                    f"Error handling command: {cmd.decode()} - hardware not responding",
                    te,
                )
            except Exception as e:
                self._error_helper(
                    message=f"Error handling command '{cmd.decode()}'", error=e
                )

    def _error_helper(
        self,
        message: str,
        error: Exception | None = None,
        level: int = logging.ERROR,
    ):
        err_msg = f"{message}: {error}" if error else message
        LOGGER.log(level=level, msg=err_msg)
        self._send_error(err_msg)

    @abstractmethod
    def connect_hardware(self) -> bool:
        """Establishes connection to the specific hardware device."""

    @abstractmethod
    def disconnect_hardware(self) -> None:
        """Disconnect from the hardware device."""
