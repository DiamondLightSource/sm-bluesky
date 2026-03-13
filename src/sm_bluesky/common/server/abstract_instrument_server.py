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
            self._conn.close()
            self._conn = None
            LOGGER.info(f"Client {addr} disconnected. Server idle.")

    def stop(self) -> None:
        pass

    def _run_command_loop(self) -> None:
        pass

    def _send_ack(self) -> None:
        pass

    def _send_error(self, error_message: str) -> None:
        pass

    def _send_response(self, response: str = "") -> None:
        pass

    @abstractmethod
    def connect_hardware(self) -> bool:
        raise NotImplementedError("Subclasses must implement connect_hardware")

    @abstractmethod
    def disconnect_hardware(self) -> None:
        raise NotImplementedError("Subclasses must implement disconnect_hardware")

    @abstractmethod
    def _handle_command(self, cmd: bytes, arg: bytes) -> None:
        raise NotImplementedError("Subclasses must implement handle_command")
