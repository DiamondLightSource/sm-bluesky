import subprocess
import sys
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from sm_bluesky import __version__
from sm_bluesky.common.cli import main


@pytest.fixture
def mock_sh_generator() -> Generator[MagicMock, None, None]:
    with patch("sm_bluesky.common.servers.GeneratorServerShanghaiTech") as mock_cls:
        yield mock_cls


def test_cli_shanghai_tech_default_arguments(mock_sh_generator: MagicMock) -> None:
    """Verify 'sm-bluesky start sh_pulse_generator' passes correct defaults."""
    mock_instance = mock_sh_generator.return_value

    main(["start", "sh_pulse_generator"])

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


def test_cli_shanghai_tech_custom_flags(mock_sh_generator: MagicMock) -> None:
    main(
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
        ]
    )

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
    main(["start", "sh_pulse_generator"])
    mock_instance.stop.assert_called_once()


@pytest.mark.parametrize(
    "command, expected_output, look_in_stderr",
    [
        ([], "sm-bluesky CLI", False),
        (
            ["junk"],
            "invalid choice: 'junk'",
            True,
        ),
        (
            ["start", "junk"],
            "invalid choice: 'junk'",
            True,
        ),
        (
            ["start"],
            "usage: ",
            False,
        ),
    ],
)
def test_cli_shows_help_on_invalid_command(
    command: list[str],
    expected_output: str,
    look_in_stderr: bool,
    capsys: pytest.CaptureFixture[str],
    mock_sh_generator: MagicMock,
) -> None:
    if look_in_stderr:
        with pytest.raises(SystemExit) as exc_info:
            main(command)
        assert exc_info.value.code == 2
    else:
        main(command)

    captured = capsys.readouterr()
    output = captured.err if look_in_stderr else captured.out

    assert expected_output in output


def test_cli_version():
    cmd = [sys.executable, "-m", "sm_bluesky", "--version"]
    assert subprocess.check_output(cmd).decode().strip() == __version__
