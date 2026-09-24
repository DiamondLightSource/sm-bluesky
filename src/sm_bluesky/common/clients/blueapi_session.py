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
        from IPython import embed

        """Start an interactive IPython shell with the BlueAPI client available."""
        embed(
            header="\nBlueAPI client ready.\n"
            'The client is available as "bc".\n'
            "Use exit() or Ctrl-D to leave.\n",
            user_ns={
                "bc": self.bc,
                "pl": self.bc.plans,
                "dev": self.bc.devices,
                "scan_data": self.data,
            },
        )

    def print_inventory(self) -> BlueapiClient:
        """Create and initialise the BlueAPI client."""

        self._install_callbacks()

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
