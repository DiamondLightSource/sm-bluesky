import re
import socket
from abc import ABC, abstractmethod
from collections.abc import Callable
from contextlib import contextmanager
from time import time
from typing import Any, TypeVar, cast

from sm_bluesky.log import LOGGER, logging

F = TypeVar("F", bound=Callable[..., Any])


def register_command(name: bytes) -> Callable[[F], F]:
    """
    Decorator to register a subclass method as an instrument command.
    """
    if not isinstance(name, bytes):
        raise TypeError("Command name must be bytes.")

    if not name:
        raise ValueError("Command name cannot be empty.")

    if re.search(rb"\s", name):
        raise ValueError("Command names must not contain whitespace.")

    def decorator(func: F) -> F:
        cast(Any, func).command_name = name
        return func

    return decorator


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
        self._current_deadline: float | None = None
        self._timeout_seconds: float = 60.0
        self.address_type = socket.AF_INET6 if ipv6 else socket.AF_INET
        self._command_registry: dict[bytes, Callable] = {
            b"connect_hardware": self.connect_hardware,
            b"disconnect_hardware": self.disconnect_hardware,
        }

        self._discover_registered_commands()

    def _discover_registered_commands(self) -> None:
        for attr_name in dir(self):
            if attr_name.startswith("__"):
                continue

            attr = getattr(self, attr_name)

            if callable(attr) and hasattr(attr, "command_name"):
                # register_command will tag the function with command_name
                cmd_bytes = attr.command_name  # type: ignore

                if cmd_bytes in self._command_registry:
                    raise ValueError(
                        f"Overwriting command '{cmd_bytes.decode()}' "
                        f"with method '{attr_name}'"
                    )

                self._command_registry[cmd_bytes] = attr
                LOGGER.debug(
                    f"Registered command '{cmd_bytes.decode()}' -> {attr_name}"
                )

    def start(self) -> None:
        """Initializes the server, connects hardware, and enters the listening loop."""

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
    def _timeout_context(self, seconds: float):
        """
        Provides a deadline for hardware operations.
        """
        self._timeout_seconds = seconds
        self._current_deadline = time() + seconds
        try:
            yield self._current_deadline
        finally:
            self._current_deadline = None

    @register_command(b"shutdown")
    def shutdown(self) -> None:
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

        parts = [part for part in line.split(b"\t") if part]
        if not parts:
            return
        cmd = parts[0]
        args = parts[1:]
        try:
            self._handle_command(cmd, args)
        except Exception as e:
            self._error_helper(message="Handler Error", error=e)

    @register_command(b"ping")
    def _send_ack(self, *args) -> None:
        self._send_response()

    def _send_error(self, error_message: str) -> None:
        if self._conn:
            self._conn.sendall(b"0\t" + error_message.encode() + b"\n")

    def _send_response(self, response: bytes = b"") -> None:
        if self._conn:
            self._conn.sendall(b"1\t" + response + b"\n")

    def _handle_command(self, cmd: bytes, args_list: list[bytes]) -> None:
        """Executes logic for a specific instrument command."""
        handler = self._command_registry.get(cmd)
        if not handler:
            self._error_helper(
                message=f"Received unknown command: '{cmd.decode()}'",
                error=Exception("Unknown command"),
                level=logging.WARNING,
            )
        else:
            try:
                with self._timeout_context(seconds=self._timeout_seconds):
                    handler(*args_list)

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

    def _check_timeout(self, context: str = "Hardware operation"):
        """Raises TimeoutError if the current operation has exceeded its deadline."""
        if hasattr(self, "_current_deadline") and self._current_deadline is not None:
            if time() > self._current_deadline:
                raise TimeoutError(f"{context} exceeded {self._timeout_seconds}s limit")

    @register_command(b"command_list")
    def _send_command_list(self, *args) -> None:
        """Returns a tab-separated list of all available commands to the client."""
        available_commands = list(self._command_registry.keys())
        payload = b"\t".join(available_commands)
        self._send_response(payload)

    @abstractmethod
    def connect_hardware(self) -> bool:
        """Establishes connection to the specific hardware device."""

    @abstractmethod
    def disconnect_hardware(self) -> None:
        """Disconnect from the hardware device."""
