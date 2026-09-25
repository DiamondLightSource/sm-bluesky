import socket


class InstrumentClient:
    """A lightweight, TCP client for interacting with AbstractInstrumentServers."""

    def __init__(self, host: str = "127.0.0.1", port: int = 7891, timeout: float = 2.0):
        self.host = host
        self.port = port
        self.timeout = timeout

    def send_payload(self, command: str, *args: str | int | float) -> str:
        """Sends a command to the server, returns the stripped text message data."""

        payload_parts = [command] + [str(arg) for arg in args]
        payload = "\t".join(payload_parts)

        if not payload.endswith("\n"):
            payload += "\n"

        try:
            with socket.create_connection(
                (self.host, self.port), timeout=self.timeout
            ) as s:
                s.sendall(payload.encode("utf-8"))

                with s.makefile("r", encoding="utf-8", errors="strict") as reader:
                    response_line = reader.readline()

                if not response_line:
                    raise ConnectionError(
                        "Server closed connection without returning data."
                    )

                response = response_line.strip()

                if "\t" in response:
                    status, data = response.split("\t", 1)
                else:
                    status, data = response, ""

                if status == "1":
                    return data
                else:
                    raise RuntimeError(f"Server Error: {data}")

        except Exception as e:
            raise ConnectionError(f"Communication layer failure: {e}") from e
