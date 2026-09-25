import os
from collections.abc import Sequence
from pathlib import Path

import click

from sm_bluesky import __version__


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, "-v", "--version", prog_name="sm-bluesky")
def cli():
    """sm-bluesky CLI"""
    pass


def main(args: Sequence[str] | None = None) -> None:
    """Argument parser for the CLI."""
    if args is not None:
        cli(args)
    else:
        cli()


@cli.group()
def start():
    """Start an instrument server"""
    pass


@cli.command()
def install_completion():
    """Install tab completion for your shell (bash/zsh)."""
    shell = os.environ.get("SHELL", "")

    if "zsh" in shell:
        profile_path = Path.home() / ".zshrc"
        command = 'eval "$(_SM_BLUESKY_COMPLETE=zsh_source sm-bluesky)"'
    elif "bash" in shell:
        profile_path = Path.home() / ".bashrc"
        command = 'eval "$(_SM_BLUESKY_COMPLETE=bash_source sm-bluesky)"'
    else:
        click.echo("Unsupported shell. Please configure manually.")
        return
    if profile_path.exists():
        content = profile_path.read_text()
        if command in content:
            click.echo("Tab completion is already installed!")
            return
    with profile_path.open("a") as f:
        f.write(f"\n# sm-bluesky tab completion\n{command}\n")

    click.echo(f"✅ Tab completion installed in {profile_path}!")
    click.echo("Please restart your terminal (or open a new tab) to use it.")


@start.command(
    name="sh_pulse_generator",
    help="Start an sh_pulse_generator instrument server",
    epilog=(
        "\b\n"
        "Example usage:\n"
        "\tsm-bluesky start sh_pulse_generator --usb-port COM4"
        " --host 192.168.1.88 --port 7891"
    ),
)
@click.option("--host", type=str, default="0.0.0.0", help="Binding host IP")
@click.option("--port", type=int, default=7891, help="TCP Port")
@click.option("--ipv6", is_flag=True, default=False, help="Enable IPv6 support")
@click.option("--usb-port", type=str, default="COM4", help="Serial USB COM port")
@click.option("--baud-rate", type=int, default=9600, help="Serial Baud rate")
@click.option("--timeout", type=float, default=1.0, help="Serial timeout duration")
@click.option(
    "--max-pulse-delay", type=int, default=1024, help="Max pulse delay configuration"
)
def start_sh_pulse_generator(
    host: str,
    port: int,
    ipv6: bool,
    usb_port: str,
    baud_rate: int,
    timeout: float,
    max_pulse_delay: int,
):
    """Start ShanghaiTech pulse generator server."""
    from sm_bluesky.common.servers import GeneratorServerShanghaiTech

    print(f"🚀 Initializing ShanghaiTech Generator on {usb_port}...")
    server = GeneratorServerShanghaiTech(
        host=host,
        port=port,
        ipv6=ipv6,
        usb_port=usb_port,
        baud_rate=baud_rate,
        timeout=timeout,
        max_pulse_delay=max_pulse_delay,
    )
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nStopping server ...")
        server.shutdown()


@start.command(
    name="blueapi",
    help="Start a BlueAPI server using a configuration file",
)
@click.option(
    "-c",
    "--config",
    type=Path,
    required=True,
    help="Path to BlueAPI YAML config file.",
)
def start_blueapi(config: Path):
    """Start a BlueAPI server."""
    import subprocess
    import sys

    print(f"🚀 Starting BlueAPI server with config: {config}")
    try:
        subprocess.run(
            [sys.executable, "-m", "blueapi", "--config", str(config), "serve"],
            check=True,
        )
    except KeyboardInterrupt:
        print("\nStopping BlueAPI server ...")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ BlueAPI server exited with error code {e.returncode}")
        sys.exit(e.returncode)


@cli.command()
@click.argument("payload", type=str)
@click.option("--host", type=str, default="127.0.0.1", help="Target server IP")
@click.option("--port", type=int, default=7891, help="Target server TCP port")
@click.option("--timeout", type=float, default=2.0, help="Socket timeout")
def send(payload: str, host: str = "127.0.0.1", port: int = 7891, timeout: float = 2.0):
    from sm_bluesky.common.clients import InstrumentClient

    print(f"Sending command:{payload} to {host}:" + f"{port}")
    try:
        parts = payload.split()
        if not parts:
            raise ValueError("Payload cannot be empty")

        command = parts[0]
        arguments = parts[1:]
        client = InstrumentClient(
            host=host,
            port=port,
            timeout=timeout,
        )

        result = client.send_payload(command, *arguments)
        print(f"✅ SUCCESS: {result}" if result else "✅ SUCCESS")
    except Exception as err:
        print(f"\u274c FAILED: {err}")


@cli.command(
    name="client",
    help="Launch an interactive IPython BlueAPI client session",
    epilog=(
        "\b\n"
        "Example usages:\n"
        "  sm-bluesky client -b p99 -s cm44186-1\n"
        "  sm-bluesky client -c /path/config.yaml -s cm44186-1\n"
    ),
)
@click.option(
    "-b", "--beamline", type=str, default=None, help="Target beamline name (e.g., iXX)."
)
@click.option(
    "-c",
    "--config",
    type=Path,
    default=None,
    help="Path to BlueAPI YAML config file.",
)
@click.option(
    "-s",
    "--session",
    type=str,
    default=None,
    help="Pre-assign the active instrument session (e.g. cm44186-1).",
)
def blueapi_client(
    beamline: str | None, config: Path | None, session: str | None
) -> None:
    """Launch an interactive IPython BlueAPI client session."""
    from sm_bluesky.common.clients import (
        BlueAPISession,
        load_config,
    )

    if not beamline and not config:
        click.echo(
            "Error: Please provide either a beamline name (-b) or a config file (-c)."
        )
        return

    app_config = load_config(
        config_path=config,
        beamline=beamline,
    )

    bs_session = BlueAPISession(
        config=app_config,
        instrument_session=session,
    )
    bs_session.start_shell()
