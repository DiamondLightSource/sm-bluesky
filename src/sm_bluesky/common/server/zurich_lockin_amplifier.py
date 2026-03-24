import functools
import inspect
from time import sleep, time
from typing import Literal

import numpy as np
from zhinst.core import ScopeModule, ziDAQServer

from sm_bluesky.common.server import AbstractInstrumentServer
from sm_bluesky.log import LOGGER


def auto_type_cast(func):
    """Automatically casts byte arguments to the types hinted
    in the function signature."""

    @functools.wraps(func)
    def wrapper(self, *args: bytes):
        sig = inspect.signature(func)
        params = list(sig.parameters.values())[1:]

        casted_args = []
        for i, arg in enumerate(args):
            if i < len(params):
                target_type = params[i].annotation
                try:
                    decoded = arg.decode("utf-8")
                    if target_type is float:
                        casted_args.append(float(decoded))
                    elif target_type is int:
                        casted_args.append(int(decoded))
                    else:
                        casted_args.append(decoded)
                except ValueError as err:
                    raise ValueError(
                        f"Argument '{arg}' cannot be converted to "
                        f"{target_type.__name__}"
                    ) from err
            else:
                casted_args.append(arg)

        return func(self, *casted_args)

    return wrapper


class HF2Server(AbstractInstrumentServer):
    """Python class to create a sever that connect to HF2 data server and listen for
    data request from client."""

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
        self._minimum_scope_wait = 0.1
        self._device: ziDAQServer | None = None
        self._scope: ScopeModule | None = None
        self._scope_frequency: float | None = None
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

    @property
    def device(self) -> ziDAQServer:
        if self._device is None:
            raise ConnectionError("Lockin amplifier not connected")
        return self._device

    @device.setter
    def device(self, value: ziDAQServer | None):
        self._device = value

    @property
    def scope(self) -> ScopeModule:
        if self._scope is None:
            raise ConnectionError(
                "Scope module not initialized. Run setupScope before using scope."
            )
        return self._scope

    @scope.setter
    def scope(self, value: ScopeModule | None):
        self._scope = value

    # --- Example Method ---

    def connect_hardware(self) -> bool:
        """Connect to Zurich Instruments HF2 Data Server."""
        try:
            self.device = ziDAQServer(self.hf2_ip, self.hf2_port, self.api_level)
            self._setup_scope()
            LOGGER.info(f"HF2 Data server connected at {self.hf2_ip}")
            return True
        except Exception as e:
            self._error_helper("HF2 Connection failed", e)
            return False

    def disconnect_hardware(self) -> None:
        """Disconnect from HF2 and cleanup modules."""
        try:
            self.device.disconnect()
            LOGGER.info("HF2 disconnected")
        except Exception as e:
            self._error_helper("Error during HF2 disconnect", e)
        finally:
            self.device = None

    # --- Hardware Logic Methods ---
    def _setup_scope(self, freq: float = 5.0, length: int = 4096, channel: int = 0):
        self.scope = self.device.scopeModule()
        self._scope_frequency = 5.0
        self.device.set(f"/{self.device_id}/scopes/0/time", freq)
        self.device.set(f"/{self.device_id}/scopes/0/length", length)
        self.device.set(f"/{self.device_id}/scopes/0/channels/0/inputselect", channel)
        self.device.set(f"/{self.device_id}/scopes/0/enable", 0)

    def _get_single_scope_shot(self) -> float:
        """Returns the mean value of a single scope shot."""
        if self._scope_frequency:
            self.device.set(f"/{self.device_id}/scopes/0/enable", 0)
            self.scope.set("scopeModule/mode", 1)
            self.scope.subscribe(f"/{self.device_id}/scopes/0/wave/")
            self.scope.execute()
            self.device.setInt(f"/{self.device_id}/scopes/0/single", 1)
            self.device.setInt(f"/{self.device_id}/scopes/0/enable", 1)
            self.device.sync()
            sleep(1.0 / self._scope_frequency + self._minimum_scope_wait)
            self.scope.finish()
            result = self.scope.read(True)
            static_mean = result[f"/{self.device_id}/scopes/0/wave"][0][0]["wave"][
                0
            ].mean()
            self.scope.unsubscribe("*")
            self.device.set(f"/{self.device_id}/scopes/0/enable", 0)
            return float(static_mean)
        else:
            raise ValueError(
                "Scope frequency not set, use 'setupScope' before taking data."
            )

    def _get_lockin_data(self, duration: float) -> tuple[float, float, float, float]:
        """Averages demodulator data over a specific duration."""
        x, y = [], []
        start_time = time()
        end_time = start_time + duration
        start_avg_time = start_time + (duration * 0.5)

        # Wait for stabilization
        while time() < start_avg_time:
            sleep(0.01)

        # Collect samples
        while time() < end_time:
            sample = self.device.getSample(f"/{self.device_id}/demods/0/sample")
            x.append(sample["x"])
            y.append(sample["y"])

        avg_x, avg_y = float(np.mean(x)), float(np.mean(y))
        r = float(np.abs(avg_x + 1j * avg_y))
        theta = float(np.rad2deg(np.arctan2(avg_y, avg_x)))
        return avg_x, avg_y, r, theta

    def _set_node(self, path: str, value: float | int, response_msg: bytes):
        if isinstance(value, int):
            self.device.setInt(f"/{self.device_id}/{path}", value)
            self._send_response(response_msg + b": %i" % value)
        else:
            self.device.setDouble(f"/{self.device_id}/{path}", value)
            self._send_response(response_msg + b": %f" % value)

    # --- Command Handlers ---
    def _get_combined_data(self, value: bytes = b"0.1"):
        duration = float(value.decode())
        x, y, r, theta = self._get_lockin_data(duration)
        static = self._get_single_scope_shot()
        response = f"{x:e}, {y:e}, {theta:f}, {static:e}, {r:e}"
        self._send_response(response.encode())

    def _set_current_range(self, value: bytes):
        raw_val = float(value)
        exponent = int(np.floor(np.log10(raw_val)))
        self.device.setDouble(f"/{self.device_id}/currins/0/range", 10**exponent)
        self._send_response(b"Current range set")

    def _set_ref_output(self, value: bytes):
        state = 1 if value.strip().lower() == b"on" else 0
        self.device.setInt(f"/{self.device_id}/sigouts/0/enables/1", state)
        self._send_response(f"Output set to {state}".encode())

    @auto_type_cast
    def _setup_scope_cmd(self, freq: float = 5.0, length: int = 4096, channel: int = 0):
        self._setup_scope(freq, length, channel)
        self._send_response(b"Scope configured")

    # Add command mappings...
    def _auto_voltage_range(self):
        self._set_node(
            path="sigins/0/autorange", value=1, response_msg=b"Auto voltage triggered"
        )

    def _auto_current_range(self):
        self._set_node(
            path="currins/0/autorange", value=1, response_msg=b"Auto current triggered"
        )

    @auto_type_cast
    def _set_time_constant(self, val: float):
        self._set_node(
            path="demods/0/timeconstant", value=val, response_msg=b"Time constant set"
        )

    @auto_type_cast
    def _set_ref_freq(self, val: float):
        self._set_node(path="oscs/0/freq", value=val, response_msg=b"Frequency set")

    @auto_type_cast
    def _set_data_rate(self, val: float):
        self._set_node(path="demods/0/rate", value=val, response_msg=b"Data rate set")

    @auto_type_cast
    def _set_ref_vpk(self, val: float):
        self._set_node(
            path="sigouts/0/amplitudes/1", value=val, response_msg=b"Ref Vpk set"
        )

    @auto_type_cast
    def _set_ref_voff(self, val: float):
        self._set_node(path="sigouts/0/offset", value=val, response_msg=b"Ref Voff set")

    @auto_type_cast
    def _set_ref_harmonic(self, val: float):
        self._set_node(
            path="demods/1/harmonic", value=val, response_msg=b"Harmonic set"
        )
