import socket
from abc import abstractmethod
from contextlib import contextmanager

from sm_bluesky.log import LOGGER


class AbstractInstrumentServer:
    def __init__(self, host: str, port: int):
        self.host: str = host
        self.port: int = port
        self._is_running: bool = False
        self._hardware_connected: bool = False
        self._server_socket: socket.socket
        self._conn: socket.socket | None = None

    def start(self) -> None:
        self._is_running = True

        self._hardware_connected = self.connect_hardware()
        if not self._hardware_connected:
            self._is_running = False
            LOGGER.error("Failed to connect hardware")
            raise RuntimeError("Failed to connect hardware")
        LOGGER.info("Hardware connected successfully")
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
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
                    self._run_command_loop()
            except TimeoutError:
                continue
            except Exception as e:
                LOGGER.error(f"Error in server loop: {e}")
                self._is_running = False

    @contextmanager
    def _manage_connection(self, client_info: tuple[socket.socket, str]):
        self._conn, addr = client_info
        LOGGER.info(f"Client {addr} connected. Server busy.")
        try:
            yield
        finally:
            self._disconnect_client()
            LOGGER.info(f"Client {addr} disconnected. Server ready.")

    def stop(self) -> None:

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

    def _run_command_loop(self) -> None:
        if self._conn is None:
            LOGGER.error("No client connection available to run command loop")
            return
        queued_data = self._conn.recv(1024).splitlines()
        if not queued_data:
            queued_data = [b"disconnect"]
        for line in queued_data:
            if b"\t" in line:
                cmd, arg = line.split(b"\t", 1)
            else:
                cmd, arg = line, b""
            self._handle_command(cmd, arg)

    def _send_ack(self) -> None:
        self._send_response()

    def _send_error(self, error_message: str) -> None:
        if self._conn:
            self._conn.sendall(b"0\t" + error_message.encode() + b"\n")

    def _send_response(self, response: str = "") -> None:
        if self._conn:
            self._conn.sendall(b"1\t" + response.encode() + b"\n")

    @abstractmethod
    def connect_hardware(self) -> bool:
        raise NotImplementedError("Subclasses must implement connect_hardware")

    @abstractmethod
    def disconnect_hardware(self) -> None:
        raise NotImplementedError("Subclasses must implement disconnect_hardware")

    @abstractmethod
    def _handle_command(self, cmd: bytes, arg: bytes) -> None:
        raise NotImplementedError("Subclasses must implement handle_command")
