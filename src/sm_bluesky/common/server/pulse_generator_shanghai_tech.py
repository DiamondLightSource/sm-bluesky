from serial import Serial

from sm_bluesky.common.server import AbstractInstrumentServer
from sm_bluesky.log import LOGGER


class GeneratorServerShanghaiTech(AbstractInstrumentServer):
    def __init__(
        self,
        host: str,
        port: int,
        ipv6: bool = False,
        usb_port: str = "COM4",
        baud_rate: int = 9600,
        timeout: float = 1.0,
    ):
        super().__init__(host, port, ipv6)
        self.usb_port: str = usb_port
        self.baud_rate: int = baud_rate
        self.timeout: float = timeout
        self.device: Serial | None = None

    def connect_hardware(self) -> bool:
        """Initialize the USB connection protocol."""
        try:
            self.device = Serial(
                port=self.usb_port, baudrate=self.baud_rate, timeout=self.timeout
            )
            self._send_response("Hardware connected successfully")
            return True
        except Exception as e:
            LOGGER.error(f"Failed to connect to hardware {e}")
            self._send_error(f"Failed to connect to hardware {e}")
            return False

    def disconnect_hardware(self):
        """Safely release the USB resource."""
        if self.device and self.device.is_open:
            try:
                self.device.close()
            except Exception as e:
                LOGGER.error(f"Error occurred while closing hardware connection {e}")
                self._send_error(
                    f"Error occurred while closing hardware connection {e}"
                )
            self._hardware_connected = False
            self.device = None
            LOGGER.info("Hardware disconnected successfully")
            self._send_response("Hardware disconnected")
        else:
            LOGGER.warning("Attempted to disconnect hardware that was not connected")
            self._send_error("Attempted to disconnect hardware that was not connected")

    def _handle_command(self, cmd: bytes, arg: bytes) -> None:
        """
        Routes incoming commands to the pulse generator.
        """
        if cmd == b"disconnect":
            self.disconnect_hardware()

        elif cmd == b"check_status":
            # TODO: Logic to get hardware status
            pass

        elif cmd == b"set_delay":
            # TODO: Logic to set delay using args
            pass

        elif cmd == b"get_delay":
            # TODO: Return current delay
            pass

        elif cmd == b"reset_output_buffer":
            # TODO: Logic to clear buffer
            pass

        elif cmd == b"pass_command":
            # TODO: Forward raw command
            pass

        else:
            pass
