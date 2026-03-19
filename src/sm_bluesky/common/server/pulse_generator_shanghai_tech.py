import logging

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
        max_pulse_delay=1024,
    ):
        super().__init__(host, port, ipv6)
        self.usb_port: str = usb_port
        self.baud_rate: int = baud_rate
        self.timeout: float = timeout
        self.max_pulse_delay: float = max_pulse_delay
        self.device: Serial

        # Expand the registry with Pulse Generator specific commands
        self._command_registry.update(
            {
                b"set_delay": self._set_delay,
                b"get_delay": self._get_delay,
                b"reset_serial_buffer": self._reset_serial_buffer,
                b"pass_command": self._passthrough,
            }
        )

    def connect_hardware(self) -> bool:
        """Initialize the USB connection protocol."""
        try:
            self.device = Serial(
                port=self.usb_port, baudrate=self.baud_rate, timeout=self.timeout
            )
            self._send_response(b"Hardware connected successfully")
            return True
        except Exception as e:
            self._error_helper(message="Failed to connect to hardware", error=e)
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
            LOGGER.info("Hardware disconnected successfully")
            self._send_response(b"Hardware disconnected")
        else:
            self._error_helper(
                message="Attempted to disconnect hardware that was not connected",
                level=logging.WARNING,
            )

    def _set_delay(self, value: bytes) -> None:

        #        try:
        delay = int(value.decode("utf-8"))
        if self.max_pulse_delay > delay >= 0:
            self._send_hardware_command(b"AT+DLSET=" + value)
            LOGGER.info(f"Setting delay to {value}")
        else:
            raise ValueError(
                f"Delay {delay} is out of bounds (0-{self.max_pulse_delay - 1})"
            )

    def _get_delay(self):
        self._send_hardware_command(b"AT+DLSET=?")
        LOGGER.info("Reading delay")

    def _reset_serial_buffer(self):
        self.device.reset_input_buffer()
        self.device.reset_output_buffer()
        LOGGER.info("Resting buffers")

    def _passthrough(self, value: bytes):
        self._send_hardware_command(value)

    def _send_hardware_command(self, cmd: bytes) -> None:
        self.device.write(cmd + b"\r\n")
        self.device.flush()
        device_respond = self.device.readline()
        self._send_response(device_respond)
