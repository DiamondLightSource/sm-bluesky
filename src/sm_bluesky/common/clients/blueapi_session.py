import json
import os
from datetime import datetime
from typing import Any

import click
from blueapi.client import BlueapiClient
from blueapi.client.event_bus import AnyEvent
from blueapi.config import ApplicationConfig
from blueapi.core import DataEvent

from .interactive_plot import InteractivePlotWindow


class BlueAPISession:
    def __init__(
        self, config: ApplicationConfig, instrument_session: str | None = None
    ):
        self.config: ApplicationConfig = config
        self.data: dict[str, dict[str, list[Any]]] = {}
        self.metadata: dict[str, dict[str, Any]] = {}
        self.current_scan_id: Any | None = None
        self._active_plot_windows: list[InteractivePlotWindow] = []
        click.echo("Connecting to BlueAPI service...")
        self.bc = BlueapiClient.from_config(self.config)
        self.bc.login()

        self._install_callbacks()
        self.print_inventory()

        if instrument_session:
            self.bc.instrument_session = instrument_session
            click.echo(f"Active instrument session: {instrument_session}")
            self._load_scan_cache()
        else:
            click.secho(
                "\n[Notice] No instrument session set. Set `bc.instrument_session ="
                " '<session_id>'` before dispatching plans.",
                fg="red",
            )

    def _get_cache_path(self) -> str | None:
        if not getattr(self.bc, "instrument_session", None):
            return None
        cache_dir = os.path.expanduser("~/.sm-bluesky/cache")
        os.makedirs(cache_dir, exist_ok=True)
        return os.path.join(cache_dir, f"{self.bc.instrument_session}_scans.jsonl")

    def _load_scan_cache(self) -> None:
        cache_file = self._get_cache_path()
        if not cache_file:
            return
        if not os.path.exists(cache_file):
            return

        try:
            with open(cache_file) as f:
                for line in f:
                    data_chunk = json.loads(line)
                    for s_id, s_data in data_chunk.items():
                        if (
                            isinstance(s_data, dict)
                            and "data" in s_data
                            and "meta" in s_data
                        ):
                            self.data[s_id] = s_data["data"]
                            self.metadata[s_id] = s_data["meta"]
                        else:
                            self.data[s_id] = s_data
            if self.data:
                click.echo(f"Loaded {len(self.data)} previous scans from cache.")
        except Exception as e:
            click.echo(f"Warning: Could not read scan cache: {e}")

    def _save_scan_to_cache(self, scan_id: str) -> None:
        cache_file = self._get_cache_path()
        if not cache_file or scan_id not in self.data:
            return

        try:
            with open(cache_file, "a") as f:
                scan_data = {
                    str(scan_id): {
                        "data": self.data[scan_id],
                        "meta": self.metadata.get(scan_id, {}),
                    }
                }
                line = json.dumps(scan_data, default=str)
                f.write(line + "\n")
        except Exception as e:
            click.echo(f"Warning: Could not write to scan cache: {e}")

    def start_shell(self) -> None:
        """Start an interactive IPython shell with the BlueAPI client available."""
        from IPython import start_ipython
        from traitlets.config import Config

        c = Config()
        c.InteractiveShellApp.exec_lines = [
            (
                "try:\n\tget_ipython().run_line_magic('matplotlib', 'auto')"
                "\n\tplot()\n"
                "except Exception as e:"
                "\n\tprint(f'Failed to start interactive plot: {e}')"
            )
        ]

        c.TerminalInteractiveShell.banner1 = (
            "\nBlueAPI client ready.\n"
            'The client is available as "bc".\n'
            "Use exit() or Ctrl-D to leave.\n"
        )

        start_ipython(
            argv=[],
            config=c,
            user_ns={
                "bc": self.bc,
                "pl": self.bc.plans,
                "show_plan": self.print_plans,
                "dev": self.bc.devices,
                "show_devices": self.print_devices,
                "scan_data": self.data,
                "metadata": self.metadata,
                "get_detector_filepath": self.get_detector_filepath,
                "plot": self.plot,
            },
        )

    def get_detector_filepath(
        self, device_name: str, scan_id: Any | None = None
    ) -> str | None:
        """Reconstruct the data file path for an area detector for a given scan."""
        s_id = (
            str(scan_id)
            if scan_id is not None
            else (
                self.current_scan_id
                or (next(reversed(self.data)) if self.data else None)
            )
        )
        if not s_id:
            return None

        start_doc = self.metadata.get(s_id, {})
        directory = start_doc.get("data_session_directory")
        template = start_doc.get("detector_file_template")
        instrument = start_doc.get("instrument")

        if not (directory and template and instrument):
            return None

        try:
            filename = template.format(
                instrument=instrument,
                scan_id=s_id,
                device_name=device_name,
            )
            return os.path.join(directory, f"{filename}.h5")
        except Exception:
            return None

    def plot(self, scan_id: Any | None = None) -> None:
        """Open an interactive plot window for multiple scans and axes."""
        self._active_plot_windows = [
            win
            for win in self._active_plot_windows
            if win.plt.fignum_exists(win.fig.number)
        ]

        try:
            window = InteractivePlotWindow(self.data, scan_id)
            self._active_plot_windows.append(window)
        except ImportError:
            pass

    def print_plans(self) -> None:
        click.echo("\nPlans available:")
        for plan in self.bc.plans:
            click.echo(f"  {plan.name}")

    def print_devices(self) -> None:
        click.echo("\nDevices available:")
        for device in self.bc.devices:
            click.echo(f"  {device.name}")

    def print_inventory(self) -> None:
        self.print_plans()
        self.print_devices()

    def _install_callbacks(self) -> None:
        """Install a callback to store the data events locally"""

        def feedback(event: AnyEvent) -> None:
            match event:
                case DataEvent(name="start", doc=start_doc):
                    scan_id = start_doc.get("scan_id")
                    uid = start_doc.get("uid")
                    time = start_doc.get("time")

                    if scan_id is not None:
                        scan_id_str = str(scan_id)
                        self.current_scan_id = scan_id_str
                        self.data[scan_id_str] = {}
                        self.metadata[scan_id_str] = dict(start_doc)

                    formatted_time = self._format_time(time) if time is not None else ""
                    click.echo(
                        f"{formatted_time} - Run started (scan_id={scan_id}, uid={uid})"
                    )

                case DataEvent(
                    name="stop",
                    doc={
                        "exit_status": status,
                        "time": time,
                        "uid": uid,
                    },
                ):
                    click.echo(
                        f"{self._format_time(time)} -"
                        f" Run complete (scan_id={self.current_scan_id}, "
                        f"uid: {uid}): {status}"
                    )
                    if self.current_scan_id is not None:
                        self._save_scan_to_cache(str(self.current_scan_id))
                    self.current_scan_id = None

                case DataEvent(
                    name="event",
                    doc={"seq_num": point, "data": event_data, "time": time},
                ):
                    if self.current_scan_id is None:
                        return

                    scan_data = self.data[self.current_scan_id]

                    for device, value in event_data.items():
                        scan_data.setdefault(device, []).append(value)

                    values = ", ".join(
                        f"{name}={value}" for name, value in event_data.items()
                    )
                    click.echo(f"{self._format_time(time)} - Point {point}: {values}")

        callback_id = self.bc.add_callback(feedback)
        click.echo(f"Installed data event callback (id={callback_id}).")

    @staticmethod
    def _format_time(timestamp: int) -> str:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
