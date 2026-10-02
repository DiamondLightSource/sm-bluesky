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
        self._bc: BlueapiClient | None = None
        self.config: ApplicationConfig = config
        self.data: dict[str, dict[str, list[Any]]] = {}
        self.current_scan_id: Any | None = None
        click.echo("Connecting to BlueAPI service...")
        self.bc = BlueapiClient.from_config(self.config)
        self.bc.login()

        self._install_callbacks()
        self.print_inventory()

        if instrument_session:
            self.bc.instrument_session = instrument_session
            click.echo(f"Active instrument session: {instrument_session}")
        else:
            click.secho(
                "\n[Notice] No instrument session set. Set `bc.instrument_session ="
                " '<session_id>'` before dispatching plans.",
                fg="red",
            )

    @property
    def bc(self) -> BlueapiClient:
        if self._bc is None:
            raise RuntimeError("BlueAPI client is not initialized.")
        return self._bc

    @bc.setter
    def bc(self, value: BlueapiClient) -> None:
        self._bc = value

    def start_shell(self) -> None:
        """Start an interactive IPython shell with the BlueAPI client available."""
        from IPython import start_ipython
        from traitlets.config import Config

        c = Config()
        c.InteractiveShellApp.exec_lines = [
            (
                "try:\n    get_ipython().run_line_magic('matplotlib', 'auto')\n"
                "    plot()\nexcept Exception as e:\n"
                "    print(f'Failed to start interactive plot: {e}')"
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
                "plot": self.plot,
            },
        )

    def plot(self, scan_id: Any | None = None) -> None:
        """Open an interactive plot window for multiple scans and axes."""
        if hasattr(self, "_active_plot_windows"):
            self._active_plot_windows = [
                win
                for win in self._active_plot_windows
                if win.plt.fignum_exists(win.fig.number)
            ]
        else:
            self._active_plot_windows = []

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
        """Install a callback to store the date event locally"""

        def feedback(event: AnyEvent) -> None:

            match event:
                case DataEvent(
                    name="start", doc={"scan_id": scan_id, "uid": uid, "time": time}
                ):
                    self.current_scan_id = scan_id
                    self.data[scan_id] = {}

                    click.echo(
                        f"{self._format_time(time)} -"
                        f" Run started (scan_id={scan_id}, uid={uid})"
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
