import os
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from sm_bluesky import __version__
from sm_bluesky.common.cli import cli


@pytest.fixture
def mock_sh_generator() -> Generator[MagicMock, None, None]:
    with patch("sm_bluesky.common.servers.GeneratorServerShanghaiTech") as mock_server:
        yield mock_server


@pytest.fixture
def mock_instrument_client() -> Generator[MagicMock, None, None]:
    with patch("sm_bluesky.common.clients.InstrumentClient") as mock_client:
        yield mock_client


def test_cli_shanghai_tech_start_default_arguments(
    mock_sh_generator: MagicMock,
) -> None:
    mock_instance = mock_sh_generator.return_value
    runner = CliRunner()

    result = runner.invoke(cli, ["start", "sh_pulse_generator"])

    assert result.exit_code == 0
    mock_sh_generator.assert_called_once_with(
        host="0.0.0.0",
        port=7891,
        ipv6=False,
        usb_port="COM4",
        baud_rate=9600,
        timeout=1.0,
        max_pulse_delay=1024,
    )
    mock_instance.start.assert_called_once()


def test_cli_shanghai_tech_start_custom_flags(mock_sh_generator: MagicMock) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "start",
            "sh_pulse_generator",
            "--host",
            "127.0.0.1",
            "--port",
            "8080",
            "--ipv6",
            "--usb-port",
            "COM9",
            "--baud-rate",
            "115200",
            "--timeout",
            "2.5",
            "--max-pulse-delay",
            "2048",
        ],
    )

    assert result.exit_code == 0
    mock_sh_generator.assert_called_once_with(
        host="127.0.0.1",
        port=8080,
        ipv6=True,
        usb_port="COM9",
        baud_rate=115200,
        timeout=2.5,
        max_pulse_delay=2048,
    )


def test_cli_handles_keyboard_interrupt(mock_sh_generator: MagicMock) -> None:
    mock_instance = mock_sh_generator.return_value
    mock_instance.start.side_effect = KeyboardInterrupt()
    runner = CliRunner()

    result = runner.invoke(cli, ["start", "sh_pulse_generator"])

    assert result.exit_code == 0
    mock_instance.shutdown.assert_called_once()


@patch("subprocess.run")
def test_start_blueapi_success(mock_subprocess_run: MagicMock) -> None:
    import sys

    runner = CliRunner()
    result = runner.invoke(cli, ["start", "blueapi", "-c", "my_config.yaml"])

    assert result.exit_code == 0
    mock_subprocess_run.assert_called_once_with(
        [sys.executable, "-m", "blueapi", "-c", "my_config.yaml", "serve"],
        check=True,
    )
    assert "🚀 Starting BlueAPI server with config: my_config.yaml" in result.output


@patch("subprocess.run")
def test_start_blueapi_keyboard_interrupt(mock_subprocess_run: MagicMock) -> None:
    mock_subprocess_run.side_effect = KeyboardInterrupt()
    runner = CliRunner()

    result = runner.invoke(cli, ["start", "blueapi", "-c", "my_config.yaml"])

    assert result.exit_code == 0
    assert "Stopping BlueAPI server ..." in result.output


@patch("subprocess.run")
def test_start_blueapi_called_process_error(mock_subprocess_run: MagicMock) -> None:
    import subprocess

    mock_subprocess_run.side_effect = subprocess.CalledProcessError(1, ["cmd"])
    runner = CliRunner()

    result = runner.invoke(cli, ["start", "blueapi", "-c", "my_config.yaml"])

    assert result.exit_code == 1
    assert "❌ BlueAPI server exited with error code 1" in result.output


@pytest.mark.parametrize(
    "command, expected_output, exit_code",
    [
        ([], "sm-bluesky CLI", 2),
        (
            ["junk"],
            "No such command 'junk'",
            2,
        ),
        (
            ["start", "junk"],
            "No such command 'junk'",
            2,
        ),
        (
            ["start"],
            "Usage: ",
            2,
        ),
    ],
)
def test_cli_shows_help_on_invalid_command(
    command: list[str],
    expected_output: str,
    exit_code: int,
) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, command)

    assert result.exit_code == exit_code
    assert expected_output in result.output


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_cli_send_command_success(
    mock_instrument_client: MagicMock,
) -> None:
    mock_instance = mock_instrument_client.return_value
    mock_instance.send_payload.return_value = "512"

    runner = CliRunner()
    result = runner.invoke(
        cli, ["send", "SET_DELAY 512", "--host", "0.0.0.0", "--port", "8888"]
    )

    assert result.exit_code == 0
    mock_instrument_client.assert_called_once_with(
        host="0.0.0.0", port=8888, timeout=2.0
    )
    mock_instance.send_payload.assert_called_once_with("SET_DELAY", "512")

    assert "Sending command:SET_DELAY 512" in result.output
    assert "SUCCESS: 512" in result.output


def test_cli_send_command_failure(
    mock_instrument_client: MagicMock,
) -> None:
    mock_instance = mock_instrument_client.return_value
    mock_instance.send_payload.side_effect = ConnectionError("Help help")

    runner = CliRunner()
    result = runner.invoke(cli, ["send", "do not matter"])

    assert result.exit_code == 0
    assert "FAILED: Help help" in result.output


def test_cli_send_empty_payload(
    mock_instrument_client: MagicMock,
) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["send", "   "])

    assert result.exit_code == 0
    assert "FAILED: Payload cannot be empty" in result.output
    mock_instrument_client.assert_not_called()


def test_cli_client_missing_args() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["client"])

    assert result.exit_code == 0
    assert (
        "Error: Please provide either a beamline name (-b) or a config file (-c)."
        in result.output
    )


@patch("sm_bluesky.common.clients.BlueAPISession")
@patch("sm_bluesky.common.clients.load_config")
def test_cli_client_with_beamline(
    mock_load_config: MagicMock, mock_blueapi_session: MagicMock
) -> None:
    runner = CliRunner()
    mock_instance = mock_blueapi_session.return_value
    mock_config = mock_load_config.return_value

    result = runner.invoke(cli, ["client", "-b", "i10", "-s", "my-session"])

    assert result.exit_code == 0
    mock_load_config.assert_called_once_with(config_path=None, beamline="i10")
    mock_blueapi_session.assert_called_once_with(
        config=mock_config, instrument_session="my-session"
    )
    mock_instance.start_shell.assert_called_once()


@patch("sm_bluesky.common.clients.BlueAPISession")
@patch("sm_bluesky.common.clients.load_config")
def test_cli_client_with_config(
    mock_load_config: MagicMock, mock_blueapi_session: MagicMock
) -> None:
    runner = CliRunner()
    mock_instance = mock_blueapi_session.return_value
    mock_config = mock_load_config.return_value

    result = runner.invoke(cli, ["client", "-c", "/path/to/config.yaml"])

    assert result.exit_code == 0
    mock_load_config.assert_called_once()

    assert str(mock_load_config.call_args[1]["config_path"]) == "/path/to/config.yaml"
    assert mock_load_config.call_args[1]["beamline"] is None

    mock_blueapi_session.assert_called_once_with(
        config=mock_config, instrument_session=None
    )
    mock_instance.start_shell.assert_called_once()


def test_install_completion_unsupported_shell():
    from sm_bluesky.common.cli import install_completion

    runner = CliRunner()
    with patch.dict(os.environ, {"SHELL": "fish"}):
        result = runner.invoke(install_completion)
        assert "Unsupported shell" in result.output


def test_main_no_args():
    from sm_bluesky.common.cli import main

    with patch("sm_bluesky.common.cli.cli") as mock_cli:
        main()
        mock_cli.assert_called_once_with()


def test_main_with_args():
    from sm_bluesky.common.cli import main

    with patch("sm_bluesky.common.cli.cli") as mock_cli:
        main(["--help"])
        mock_cli.assert_called_once_with(["--help"])


def test_install_completion_zsh_already_installed():
    from sm_bluesky.common.cli import install_completion

    runner = CliRunner()
    with (
        patch.dict(os.environ, {"SHELL": "/bin/zsh"}),
        patch("pathlib.Path.exists", return_value=True),
        patch(
            "pathlib.Path.read_text",
            return_value='eval "$(_SM_BLUESKY_COMPLETE=zsh_source sm-bluesky)"',
        ),
    ):
        result = runner.invoke(install_completion)
        assert "already installed" in result.output


def test_install_completion_bash_success(tmp_path: Path):
    from sm_bluesky.common.cli import install_completion

    runner = CliRunner()
    bashrc = tmp_path / ".bashrc"
    bashrc.write_text("some content")

    with (
        patch.dict(os.environ, {"SHELL": "/bin/bash"}),
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        result = runner.invoke(install_completion)
        assert "Tab completion installed" in result.output
        content = bashrc.read_text()
        assert 'eval "$(_SM_BLUESKY_COMPLETE=bash_source sm-bluesky)"' in content


def test_cli_group_callback():
    from sm_bluesky.common.cli import cli, start

    assert cli.callback is not None
    cli.callback()
    assert start.callback is not None
    start.callback()
