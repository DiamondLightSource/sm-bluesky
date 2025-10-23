import pytest
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
from dodal.testing import patch_all_motors, patch_motor
from ophyd_async.core import init_devices


@pytest.fixture
def slits() -> I10Slits:
    with init_devices(mock=True):
        slits = I10Slits("TEST:")
    patch_all_motors(slits)
    return slits


@pytest.fixture
def det_slits() -> DetSlits:
    with init_devices(mock=True):
        det_slits = DetSlits("TEST:")
    patch_all_motors(det_slits)
    return det_slits


@pytest.fixture
def pa_stage() -> PaStage:
    with init_devices(mock=True):
        pa_stage = PaStage("TEST:")
    patch_all_motors(pa_stage)
    return pa_stage


@pytest.fixture
def pin_hole() -> XYStage:
    with init_devices(mock=True):
        pin_hole = XYStage("TEST:")
    patch_motor(pin_hole.y)
    patch_motor(
        pin_hole.x,
        initial_position=1,
        velocity=2.78,
        low_limit_travel=0,
        high_limit_travel=150,
    )
    return pin_hole


@pytest.fixture
def diffractometer() -> Diffractometer:
    with init_devices(mock=True):
        diffractometer = Diffractometer("TEST:")
    patch_all_motors(diffractometer)
    return diffractometer


@pytest.fixture
def sample_stage() -> XYZStage:
    with init_devices(mock=True):
        sample_stage = XYZStage("TEST:")
    patch_all_motors(sample_stage)
    return sample_stage


@pytest.fixture
def rasor_det_scalers() -> RasorScalerCard1:
    with init_devices(mock=True):
        rasor_det_scalers = RasorScalerCard1("TEST:")
    patch_all_motors(rasor_det_scalers)
    return rasor_det_scalers


@pytest.fixture
def rasor_femto() -> RasorFemto:
    with init_devices(mock=True):
        rasor_femto = RasorFemto("TEST:")
    patch_all_motors(rasor_femto)
    return rasor_femto


@pytest.fixture
def rasor_femto_pa_scaler_det(
    rasor_det_scalers: RasorScalerCard1, rasor_femto: RasorFemto
) -> CurrentAmpDet:
    with init_devices(mock=True):
        rasor_femto_pa_scaler_det = CurrentAmpDet(
            current_amp=rasor_femto.ca1,
            counter=rasor_det_scalers.det,
        )
    patch_all_motors(rasor_femto_pa_scaler_det)
    return rasor_femto_pa_scaler_det
