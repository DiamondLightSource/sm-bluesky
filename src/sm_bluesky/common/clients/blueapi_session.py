from datetime import datetime
from pathlib import Path
from typing import Any

import click
from blueapi.client import BlueapiClient
from blueapi.client.event_bus import AnyEvent
from blueapi.config import (
    ApplicationConfig,
    ConfigLoader,
    HttpUrl,
    RestConfig,
    StompConfig,
    TcpUrl,
)
from blueapi.core import DataEvent


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
        from IPython import embed
        from traitlets.config import Config

        c = Config()
        c.InteractiveShellApp.exec_lines = [
            "try:",
            "    %matplotlib auto",
            "except Exception:",
            "    pass",
        ]

        embed(
            config=c,
            header="\nBlueAPI client ready.\n"
            'The client is available as "bc".\n'
            "Use exit() or Ctrl-D to leave.\n",
            user_ns={
                "bc": self.bc,
                "pl": self.bc.plans,
                "dev": self.bc.devices,
                "scan_data": self.data,
                "plot": self.plot,
            },
        )

    def plot(
        self, x: str | None = None, y: str | None = None, scan_id: Any | None = None
    ) -> None:
        """Plot x vs y from the scan data."""
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            click.secho(
                "matplotlib is required for plotting. Install it to use this feature.",
                fg="red",
            )
            return

        target_scan_id = scan_id or self.current_scan_id
        if target_scan_id is None and self.data:
            target_scan_id = list(self.data.keys())[-1]

        if target_scan_id is None:
            click.secho("No scan data available to plot.", fg="red")
            return

        if target_scan_id not in self.data:
            click.secho(f"Scan ID {target_scan_id} not found in data.", fg="red")
            return

        scan_data = self.data[target_scan_id]
        available_fields = list(scan_data.keys())

        if not available_fields:
            click.secho(f"No fields available in scan {target_scan_id}.", fg="red")
            return

        if x is None and y is None:
            if len(available_fields) >= 2:
                x_key = available_fields[0]
                y_key = available_fields[1]
            else:
                x_key = None
                y_key = available_fields[0]
        elif y is None:
            y_key = x
            x_key = None
        else:
            x_key = x
            y_key = y

        if y_key not in scan_data:
            click.secho(
                f"Data for '{y_key}' not found in scan {target_scan_id}.", fg="red"
            )
            click.echo(f"Available fields: {available_fields}")
            return

        if x_key is not None and x_key not in scan_data:
            click.secho(
                f"Data for '{x_key}' not found in scan {target_scan_id}.", fg="red"
            )
            click.echo(f"Available fields: {available_fields}")
            return

        y_data = scan_data[y_key]

        if x_key is not None:
            x_data = scan_data[x_key]
            min_len = min(len(x_data), len(y_data))
            x_plot = x_data[:min_len]
            y_plot = y_data[:min_len]
            xlabel = x_key
        else:
            x_plot = list(range(1, len(y_data) + 1))
            y_plot = y_data
            xlabel = "Point number"

        plt.figure()
        plt.plot(x_plot, y_plot, marker="o")
        plt.xlabel(xlabel)
        plt.ylabel(y_key)
        title_x = xlabel if x_key is not None else "point number"
        plt.title(f"Scan {target_scan_id}: {title_x} vs {y_key}")
        plt.grid(True)
        plt.show(block=False)

    def print_inventory(self) -> BlueapiClient:
        """Print available plans and devices."""
        click.echo("\nPlans available:")
        for plan in self.bc.plans:
            click.echo(f"  {plan.name}")

        click.echo("\nDevices available:")
        for device in self.bc.devices:
            click.echo(f"  {device.name}")
        return self.bc

    def _install_callbacks(self) -> None:
        """Install a callback which displays run progress."""

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


def load_config(
    config_path: Path | None = None,
    beamline: str | None = None,
) -> ApplicationConfig:
    """Load configuration from file orCLI beamline flag"""

    if config_path is not None:
        print(f"Loading configuration from file: {config_path}")
        loader = ConfigLoader(ApplicationConfig)
        loader.use_values_from_yaml(config_path)
        return loader.load()

    target_beamline = beamline

    if not target_beamline:
        raise ValueError(
            "No beamline specified. Please provide either:\n"
            "  --beamline / -b <beamline_name>\n"
            "  --config / -c <path_to_yaml>\n"
        )

    print(f"Connecting using default config for beamline: {target_beamline}")

    return ApplicationConfig(
        api=RestConfig(url=HttpUrl(f"https://{target_beamline}-blueapi.diamond.ac.uk")),
        stomp=StompConfig(
            enabled=True,
            url=TcpUrl(f"tcp://{target_beamline}-rabbitmq-daq.diamond.ac.uk:61613"),
        ),
    )
