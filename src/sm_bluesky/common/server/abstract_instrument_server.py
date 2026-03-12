from abc import abstractmethod
from socket import socket


class AbstractInstrumentServer:
    def __init__(self, host: str, port: int):
        self.host: str = host
        self.port: int = port
        self._is_running: bool = False
        self._hardwarde_connected: bool = False
        self._server_socket: socket

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def _run_command_loop(self) -> None:
        pass

    def _send_ack(self) -> None:
        pass

    def _send_error(self, error_message: str) -> None:
        pass

    def _send_response(self, response: str) -> None:
        pass

    @abstractmethod
    def connect_hardware(self) -> None:
        raise NotImplementedError("Subclasses must implement connect_hardware")

    @abstractmethod
    def disconnect_hardware(self) -> None:
        raise NotImplementedError("Subclasses must implement disconnect_hardware")

    @abstractmethod
    def _handle_command(self, cmd: bytes, arg: bytes) -> None:
        raise NotImplementedError("Subclasses must implement handle_command")
