import subprocess
import sys

from sm_bluesky import __version__


def test_cli_version():
    cmd = [sys.executable, "-m", "sm_bluesky", "--version"]
    assert subprocess.check_output(cmd).decode().strip() == __version__
