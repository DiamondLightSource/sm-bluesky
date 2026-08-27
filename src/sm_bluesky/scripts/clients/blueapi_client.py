"""
Connect to real beamline:
$ export BEAMLINE=iXX
$ python -i src/sm_bluesky/scripts/clients/blueapi_client.py

Connect to beamline in mock mode
1. Create a config file. Example:

api:
    url: http://0.0.0.0:8000
env:
    metadata:
        instrument: iXX
    sources:
        - kind: deviceManager
        module: dodal.beamlines.iXX
        mock: True
        - kind: planFunctions
        module: dodal.plans
        - kind: planFunctions
        module: dodal.plan_stubs.wrapped
stomp:
    enabled: true
    url: tcp://localhost:61613/

2. In one termianl, start a mock server.
$ uv run blueapi -c /path/config.yaml

3. In another terminal, start the client script and point to same config
$ python -i src/sm_bluesky/scripts/clients/blueapi_client.py --config /path/config.yaml
"""

import argparse
from datetime import datetime
from os import environ
from pathlib import Path

from blueapi.client import BlueapiClient
from blueapi.client.event_bus import AnyEvent
from blueapi.config import ApplicationConfig, HttpUrl, RestConfig, StompConfig, TcpUrl
from blueapi.core.bluesky_types import DataEvent


def _default_config(bl: str) -> ApplicationConfig:
    return ApplicationConfig(
        api=RestConfig(url=HttpUrl(f"https://{bl}-blueapi.diamond.ac.uk")),
        stomp=StompConfig(
            enabled=True,
            url=TcpUrl(f"tcp://{bl}-rabbitmq-daq.diamond.ac.uk:61613"),
        ),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to a custom BlueAPI configuration file.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.config:
        print(f"Starting BlueapiClient from config file {args.config}.")
        bc = BlueapiClient.from_config_file(args.config)
    else:
        BEAMLINE = environ.get("BEAMLINE")
        if BEAMLINE is None:
            raise RuntimeError("BEAMLINE environment variable not set.")
        print(f"Starting BlueapiClient for {BEAMLINE}.")
        bc = BlueapiClient.from_config(_default_config(BEAMLINE))
    print('Created BlueapiClient "bc" object.')
    print("Logging in...")
    bc.login()

    def _feedback(evt: AnyEvent):
        match evt:
            case DataEvent(name="start"):
                print("Run started")
            case DataEvent(name="stop", doc={"exit_status": status}):
                print("Run complete: ", status)
            case DataEvent(
                name="event", doc={"seq_num": point, "data": data, "time": time}
            ):
                time = datetime.fromtimestamp(time).strftime("%Y-%m-%d %H:%M:%S")
                values = ", ".join(f"{name}={value}" for name, value in data.items())
                print(f"{time} - Point {point}: {values}")

    feedback_id = bc.add_callback(_feedback)
    print("Installed feedback.")

    print("\nGetting devices and plans...")
    devs = bc.devices
    plans = bc.plans
    print(devs)
    print(plans)

    print("Please remember to configure the correct instrument session for bc.")
