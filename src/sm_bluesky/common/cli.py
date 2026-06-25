from argparse import ArgumentParser
from collections.abc import Sequence

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
    start_parser = subparsers.add_parser("start", help="Start an instrument server")

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
                server.stop()
        else:
            start_parser.print_help()

    else:
        parser.print_help()
