import re
import time
from datetime import datetime
from io import TextIOWrapper

ANSI_ESCAPE = re.compile(
    r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1B\\))"
)


def format_time(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


class Tee:
    """Write output to both the original stream and a log file."""

    def __init__(self, stream, logfile: TextIOWrapper):
        self.stream = stream
        self.logfile = logfile
        self._buffer = ""

    def write(self, text: str) -> int:
        # Preserve the terminal's normal behaviour.
        self.stream.write(text)

        # Strip terminal control sequences from the log copy.
        clean_text = ANSI_ESCAPE.sub("", text)
        clean_text = clean_text.replace("\b", "").replace("\r", "")

        self._buffer += clean_text

        # Write complete lines, timestamping each one.
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            t = format_time(time.time())
            self.logfile.write(f"{t}: {line}\n")

        self.logfile.flush()
        return len(text)

    def flush(self):
        self.stream.flush()
        self.logfile.flush()

    def isatty(self):
        return self.stream.isatty()

    def fileno(self):
        return self.stream.fileno()

    @property
    def encoding(self):
        return self.stream.encoding

    @property
    def errors(self):
        return self.stream.errors
