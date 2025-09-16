import pytest
from bluesky import RunEngine
from dodal.devices.current_amplifiers import CurrentAmpDet
from dodal.devices.i10.rasor.rasor_current_amp import RasorFemto
from dodal.devices.i10.rasor.rasor_motors import (
    DetSlits,
    Diffractometer,
    PaStage,
)
from dodal.devices.i10.rasor.rasor_scaler_cards import RasorScalerCard1
from dodal.devices.i10.slits import I10Slits
from dodal.devices.motors import XYStage, XYZStage
from dodal.testing import patch_all_motors
from ophyd_async.core import init_devices


@pytest.fixture
def slits(RE: RunEngine) -> I10Slits:
    with init_devices(mock=True):
        slits = I10Slits("TEST:")
    patch_all_motors(slits)
    return slits


@pytest.fixture
def det_slits(RE: RunEngine) -> DetSlits:
    with init_devices(mock=True):
        det_slits = DetSlits("TEST:")
    patch_all_motors(det_slits)
    return det_slits


@pytest.fixture
def pa_stage(RE: RunEngine) -> PaStage:
    with init_devices(mock=True):
        pa_stage = PaStage("TEST:")
    patch_all_motors(pa_stage)
    return pa_stage


@pytest.fixture
def pin_hole(RE: RunEngine) -> XYStage:
    with init_devices(mock=True):
        pin_hole = XYStage("TEST:")
    patch_all_motors(pin_hole)
    return pin_hole


@pytest.fixture
def diffractometer(RE: RunEngine) -> Diffractometer:
    with init_devices(mock=True):
        diffractometer = Diffractometer("TEST:")
    patch_all_motors(diffractometer)
    return diffractometer


@pytest.fixture
def sample_stage(RE: RunEngine) -> XYZStage:
    with init_devices(mock=True):
        sample_stage = XYZStage("TEST:")
    patch_all_motors(sample_stage)
    return sample_stage


@pytest.fixture
def rasor_det_scalers(RE: RunEngine) -> RasorScalerCard1:
    with init_devices(mock=True):
        rasor_det_scalers = RasorScalerCard1("TEST:")
    patch_all_motors(rasor_det_scalers)
    return rasor_det_scalers


@pytest.fixture
def rasor_femto(RE: RunEngine) -> RasorFemto:
    with init_devices(mock=True):
        rasor_femto = RasorFemto("TEST:")
    patch_all_motors(rasor_femto)
    return rasor_femto


@pytest.fixture
def rasor_femto_pa_scaler_det(
    RE: RunEngine, rasor_det_scalers: RasorScalerCard1, rasor_femto: RasorFemto
) -> CurrentAmpDet:
    with init_devices(mock=True):
        rasor_femto_pa_scaler_det = CurrentAmpDet(
            current_amp=rasor_femto.ca1,
            counter=rasor_det_scalers.det,
        )
    patch_all_motors(rasor_femto_pa_scaler_det)
    return rasor_femto_pa_scaler_det
