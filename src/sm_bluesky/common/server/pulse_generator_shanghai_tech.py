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
        max_delay=1024,
    ):
        super().__init__(host, port, ipv6)
        self.usb_port: str = usb_port
        self.baud_rate: int = baud_rate
        self.timeout: float = timeout
        self.max_pulse_delay: float = max_delay
        self.device: Serial | None = None

        # Expand the registry with Pulse Generator specific commands
        self._command_registry.update(
            {
                b"set_delay": self._set_delay,
                b"get_delay": self._get_delay,
                b"reset_output_buffer": self._reset_buffer,
                b"pass_command": self._passthrough,
            }
        )

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

    def _set_delay(self, value: bytes) -> None:
        delay = int(value.decode("utf-8"))
        if 1024 > delay >= 0 and self.device is not None:
            try:
                self.device.write(b"AT+DLSET=" + value + b"\r\n")
                self._send_response(self.device.readline().decode("utf-8").strip())
            except Exception as e:
                self._error_helper(message="Set delay failed", error=e)

        else:
            self._send_error("Delay must be between 0 and 1023")
            LOGGER.error("Delay must be between 0 and 1023")

    def _get_delay(self):
        if self.device is not None:
            self.device.write(b"AT+DLSET=?\r\n")
            self._send_response(self.device.readline().decode("utf-8").strip())

        else:
            self._send_error("Fail to read delay")
