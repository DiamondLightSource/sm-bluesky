from argparse import ArgumentParser
from collections.abc import Sequence
from pathlib import Path

from sm_bluesky import __version__

__all__ = ["main"]


def main(args: Sequence[str] | None = None) -> None:
    """Argument parser for the CLI."""
    parser = ArgumentParser(description="sm-bluesky CLI")
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=__version__,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # ----------------- start command ----------------------------------------------
    start_parser = subparsers.add_parser(
        "start",
        help="Start an instrument server",
        epilog="Example usage:\n  sm-bluesky start sh_pulse_generator --usb-port COM4 "
        "--host 192.168.1.88 --port 7891 ",
    )
    server_subparsers = start_parser.add_subparsers(
        dest="server_type", help="Server types"
    )

    # --- config for shanghaiTech pulse generator ---
    sh_parser = server_subparsers.add_parser(
        "sh_pulse_generator", help="Launch ShanghaiTech pulse Generator Server"
    )
    sh_parser.add_argument(
        "--host", type=str, default="0.0.0.0", help="Binding host IP"
    )
    sh_parser.add_argument("--port", type=int, default=7891, help="TCP Port")
    sh_parser.add_argument("--ipv6", action="store_true", help="Enable IPv6 support")
    sh_parser.add_argument(
        "--usb-port", type=str, default="COM4", help="Serial USB COM port"
    )
    sh_parser.add_argument(
        "--baud-rate", type=int, default=9600, help="Serial Baud rate"
    )
    sh_parser.add_argument(
        "--timeout", type=float, default=1.0, help="Serial timeout duration"
    )
    sh_parser.add_argument(
        "--max-pulse-delay",
        type=int,
        default=1024,
        help="Max pulse delay configuration",
    )

    # ----------------- send command ----------------------------------------------
    """Quick command line to interact with server """
    send_parser = subparsers.add_parser(
        "send",
        help="Send a single text command to a running server",
        epilog='Example usage:\n  sm-bluesky send "SET_DELAY 512" --host 192.168.1.88'
        " --port 8888",
    )
    send_parser.add_argument(
        "payload",
        type=str,
        help='The command and arguments to send (e.g."SET_DELAY 512" or '
        '"command_list")',
    )
    send_parser.add_argument(
        "--host", type=str, default="127.0.0.1", help="Target server IP"
    )
    send_parser.add_argument(
        "--port", type=int, default=7891, help="Target server TCP port"
    )
    send_parser.add_argument(
        "--timeout", type=float, default=2.0, help="Socket timeout"
    )
    # ----------------- client command --------------------------------------------
    client_parser = subparsers.add_parser(
        "client",
        help="Launch an interactive IPython BlueAPI client session",
        epilog=(
            "Example usages:\n"
            "  sm-bluesky client -s cm44186-1\n"
            "  sm-bluesky client --config /path/config.yaml -s cm44186-1\n"
            "  sm-bluesky client -s cm44186-1 -p dcm_energy det1\n"
        ),
    )
    client_parser.add_argument(
        "-b",
        "--beamline",
        type=str,
        default=None,
        help="Target beamline name (e.g., iXX). Overrides $BEAMLINE if provided.",
    )
    client_parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=None,
        help="Path to BlueAPI YAML config file (overrides beamline setting).",
    )
    client_parser.add_argument(
        "-s",
        "--session",
        dest="instrument_session",
        type=str,
        default=None,
        help="Pre-assign the active instrument session (e.g. cm44186-1).",
    )
    client_parser.add_argument(
        "-p",
        "--live-plot",
        nargs=2,
        metavar=("X_AXIS", "Y_AXIS"),
        help="Configure real-time plotting for two incoming axes (e.g. -p motor det).",
    )
    # ----------------- parsing & routing -----------------------------------------
    parsed_args = parser.parse_args(args)

    if parsed_args.command == "start":
        if parsed_args.server_type == "sh_pulse_generator":
            from sm_bluesky.common.servers import GeneratorServerShanghaiTech

            print(
                f"🚀 Initializing ShanghaiTech Generator on {parsed_args.usb_port}..."
            )
            server = GeneratorServerShanghaiTech(
                host=parsed_args.host,
                port=parsed_args.port,
                ipv6=parsed_args.ipv6,
                usb_port=parsed_args.usb_port,
                baud_rate=parsed_args.baud_rate,
                timeout=parsed_args.timeout,
                max_pulse_delay=parsed_args.max_pulse_delay,
            )
            try:
                server.start()
            except KeyboardInterrupt:
                print("\nStopping server ...")
                server.shutdown()
        else:
            start_parser.print_help()
    elif parsed_args.command == "send":
        from sm_bluesky.common.clients import InstrumentClient

        print(
            f"Sending command:{parsed_args.payload} to {parsed_args.host}:"
            + f"{parsed_args.port}"
        )
        try:
            parts = parsed_args.payload.split()
            if not parts:
                raise ValueError("Payload cannot be empty")

            command = parts[0]
            arguments = parts[1:]
            client = InstrumentClient(
                host=parsed_args.host,
                port=parsed_args.port,
                timeout=parsed_args.timeout,
            )

            result = client.send_payload(command, *arguments)
            print(f"✅ SUCCESS: {result}" if result else "✅ SUCCESS")
        except Exception as err:
            print(f"\u274c FAILED: {err}")
    elif parsed_args.command == "client":
        from sm_bluesky.common.clients import (
            BlueAPISession,
            load_config,
        )

        if not parsed_args.beamline and not parsed_args.config:
            client_parser.print_help()
            return

        app_config = load_config(
            config_path=parsed_args.config,
            beamline=parsed_args.beamline,
        )

        session = BlueAPISession(
            config=app_config,
            instrument_session=parsed_args.instrument_session,
        )
        session.start_shell()
    else:
        parser.print_help()
