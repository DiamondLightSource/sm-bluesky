"""
Start this script by running:
$ python -i src/sm_bluesky/clients/blueapi_client.py
"""

from os import environ

from blueapi.client import BlueapiClient
from blueapi.config import ApplicationConfig, HttpUrl, RestConfig, StompConfig, TcpUrl
from blueapi.core.bluesky_types import DataEvent

if __name__ == "__main__":
    BEAMLINE = environ.get("BEAMLINE")
    if BEAMLINE is None:
        raise RuntimeError("BEAMLINE environment variable not set.")

    print(f"Starting BlueAPI client for {BEAMLINE}.")
    bc = BlueapiClient.from_config(
        ApplicationConfig(
            api=RestConfig(url=HttpUrl(f"https://{BEAMLINE}-blueapi.diamond.ac.uk")),
            stomp=StompConfig(
                enabled=True,
                url=TcpUrl(f"tcp://{BEAMLINE}-rabbitmq-daq.diamond.ac.uk:61613"),
            ),
        )
    )
    print('Created BlueapiClient "bc" object.')
    print("Logging in...")
    bc.login()

    def _feedback(evt):
        match evt:
            case DataEvent(name="start"):
                print("Run started")
            case DataEvent(name="stop", doc={"exit_status": status}):
                print("Run complete: ", status)
            case DataEvent(name="event", doc={"seq_num": point, "data": data}):
                print(f"    Point {point}: {data}")

    feedback_id = bc.add_callback(_feedback)
    print("Installed feedback.")

    print("\nGetting devices and plans...")
    devs = bc.devices
    plans = bc.plans
    print(devs)
    print(plans)

    print("Please remember to configure the correct instrument session for bc.")
