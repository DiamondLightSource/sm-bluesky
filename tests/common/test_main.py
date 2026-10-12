import runpy
import sys
from unittest.mock import patch

import pytest


def test_main_module_execution():
    """Test that `python -m sm_bluesky` CLI entrypoint."""
    with patch("sys.argv", ["sm-bluesky", "--version"]):
        if "sm_bluesky.__main__" in sys.modules:
            del sys.modules["sm_bluesky.__main__"]

        with pytest.raises(SystemExit) as exc_info:
            runpy.run_module("sm_bluesky.__main__", run_name="__main__")

        assert exc_info.value.code == 0
