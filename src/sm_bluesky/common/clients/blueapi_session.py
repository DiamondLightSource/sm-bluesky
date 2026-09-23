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


class BlueAPISessionClient:
    def __init__(self):
        self._bc: BlueapiClient | None = None
        self.data: dict[str, dict[str, list[Any]]] = {}

    @property
    def bc(self) -> BlueapiClient:
        if self._bc is None:
            raise RuntimeError("BlueAPI client is not initialized.")
        return self._bc

    @bc.setter
    def bc(self, value: BlueapiClient) -> None:
        self._bc = value

    def _set_live_config(self, beamline: str) -> ApplicationConfig:
        return ApplicationConfig(
            api=RestConfig(
                url=HttpUrl(f"https://{beamline}-blueapi.diamond.ac.uk"),
            ),
            stomp=StompConfig(
                enabled=True,
                url=TcpUrl(f"tcp://{beamline}-rabbitmq-daq.diamond.ac.uk:61613"),
            ),
        )

    def _set_config_from_file(self, config_path: Path | None) -> ApplicationConfig:
        if config_path is None:
            raise RuntimeError("config_path is not provided.")

        if config_path.exists():
            print(f"Starting BlueAPI client from config file {config_path}.")
            loader = ConfigLoader(ApplicationConfig)
            loader.use_values_from_yaml(config_path)
            return loader.load()
        raise FileNotFoundError("Path file not found.")

    def _start_interactive_shell(self) -> None:
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

    def _setup_client(self, config: ApplicationConfig) -> BlueapiClient:
        """Create and initialise the BlueAPI client."""
        self.bc = BlueapiClient.from_config(config)
        click.echo("Logging in...")
        self.bc.login()

        self._install_feedback_callback()

        click.echo("\nPlans available:")
        for plan in self.bc.plans:
            click.echo(f"  {plan.name}")

        click.echo("\nDevices available:")
        for device in self.bc.devices:
            click.echo(f"  {device.name}")

        click.echo(
            "\nPlease remember to configure the correct "
            "`bc.instrument_session` before running a plan."
        )
        return self.bc

    def _install_feedback_callback(self) -> None:
        """Install a callback which displays run progress."""

        current_scan_id: Any | None = None

        def feedback(event: AnyEvent) -> None:
            nonlocal current_scan_id

            match event:
                case DataEvent(
                    name="start", doc={"scan_id": scan_id, "uid": uid, "time": time}
                ):
                    current_scan_id = scan_id
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
                        f" Run complete (scan_id={current_scan_id}, "
                        f"uid: {uid}): {status}"
                    )
                    current_scan_id = None

                case DataEvent(
                    name="event",
                    doc={"seq_num": point, "data": event_data, "time": time},
                ):
                    if current_scan_id is None:
                        return

                    scan_data = self.data[current_scan_id]

                    for device, value in event_data.items():
                        scan_data.setdefault(device, []).append(value)

                    values = ", ".join(
                        f"{name}={value}" for name, value in event_data.items()
                    )
                    click.echo(f"{self._format_time(time)} - Point {point}: {values}")

        callback_id = self.bc.add_callback(feedback)
        click.echo(f"Installed data event callback (id={callback_id}).")

    def _format_time(self, timestamp: int) -> str:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
