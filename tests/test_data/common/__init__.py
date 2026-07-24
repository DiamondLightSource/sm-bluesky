from os import fspath
from os.path import join
from pathlib import Path

LOOKUP_TABLE_PATH = fspath(Path(__file__).parent)
ID_ENERGY_2_GAP_CALIBRATIONS_CSV = join(
    LOOKUP_TABLE_PATH, "IDEnergy2GapCalibrations.csv"
)
ID_ENERGY_2_PHASE_CALIBRATIONS_CSV = join(
    LOOKUP_TABLE_PATH, "IDEnergy2PhaseCalibrations.csv"
)

__all__ = [
    "LOOKUP_TABLE_PATH",
    "ID_ENERGY_2_GAP_CALIBRATIONS_CSV",
    "ID_ENERGY_2_PHASE_CALIBRATIONS_CSV",
]
