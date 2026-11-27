from ophyd_async.core import StandardReadable, soft_signal_rw
from ophyd_async.core import StandardReadableFormat as Format


class FakeDetector(StandardReadable):
    """Readable with a single settable `value` signal, for feeding known data
    into plans under test."""

    def __init__(self, name: str = "") -> None:
        with self.add_children_as_readables(Format.HINTED_SIGNAL):
            self.value = soft_signal_rw(float)
        super().__init__(name=name)
