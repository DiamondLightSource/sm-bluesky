import logging
from time import sleep, time
from typing import Literal

import numpy as np
import zhinst.core

from sm_bluesky.common.server import AbstractInstrumentServer
from sm_bluesky.log import LOGGER


class HF2Server(AbstractInstrumentServer):
    api_level: Literal[0, 1, 4, 5, 6]

    def __init__(
        self,
        host: str = "",
        port: int = 7891,
        hf2_ip: str = "172.23.110.84",
        hf2_port: int = 8004,
        api_level: Literal[0, 1, 4, 5, 6] = 6,
        device_id: str = "dev4206",
    ):
        super().__init__(host, port)
        self.hf2_ip = hf2_ip
        self.hf2_port = hf2_port
        self.api_level = api_level
        self.device_id = device_id

        self.daq: zhinst.core.ziDAQServer | None = None
        self.scope: zhinst.core.ScopeModule | None = None

        # Register HF2 specific commands
        self._command_registry.update(
            {
                b"getData": self._get_combined_data,
                b"autoVoltageInRange": self._auto_voltage_range,
                b"setTimeConstant": self._set_time_constant,
                b"setDataRate": self._set_data_rate,
                b"setCurrentInRange": self._set_current_range,
                b"autoCurrentInRange": self._auto_current_range,
                b"setRefFreq": self._set_ref_freq,
                b"setRefV": self._set_ref_vpk,
                b"setRefVoff": self._set_ref_voff,
                b"setsRefOutSwitch": self._set_ref_output,
                b"setsRefHarm": self._set_ref_harmonic,
                b"setupScope": self._setup_scope_cmd,
            }
        )

    def connect_hardware(self) -> bool:
        """Connect to Zurich Instruments HF2 Data Server."""
        return False

    def disconnect_hardware(self) -> None:
        """Disconnect from HF2 and cleanup modules."""


    # --- Hardware Logic Methods ---

    def _setup_scope(self, freq: float = 5.0, length: int = 4096, channel: int = 0):


    def _get_single_scope_shot(self) -> float:
        """Returns the mean value of a single scope shot."""


    def _get_lockin_data(self, duration: float) -> Tuple[float, float, float, float]:
        """Averages demodulator data over a specific duration."""



    # --- Command Handlers ---

    def _get_combined_data(self, value: bytes = b"0.1"):
        """Handles 'getData' command."""


    def _set_ref_freq(self, value: bytes):


    def _set_current_range(self, value: bytes):


    def _set_ref_output(self, value: bytes):


    def _setup_scope_cmd(self, args: bytes):
        """Expects: 'freq\tlength\tchannel'"""

    # Add other simple mappings...
    def _auto_voltage_range(self):


    def _set_time_constant(self, val: bytes):

    def _set_data_rate(self, val: bytes):


    def _auto_current_range(self):

    def _set_ref_vpk(self, val: bytes):

    def _set_ref_voff(self, val: bytes):


    def _set_ref_harmonic(self, val: bytes):
