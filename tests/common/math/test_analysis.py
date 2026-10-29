import numpy as np
import pytest
from lmfit.model import ModelResult

from sm_bluesky.common.math.analysis import (
    DerivativeResult,
    calculate_com,
    calculate_derivatives,
    fit_gaussian,
)


def test_fit_gaussian_clean_peak() -> None:
    true_x0 = 12.4
    true_sigma = 1.8
    true_amplitude = 150.0
    true_baseline = 10.0
    true_fwhm = 2.354820045 * true_sigma

    x = np.linspace(5, 20, 151)
    y = true_baseline + (true_amplitude / (true_sigma * np.sqrt(2 * np.pi))) * np.exp(
        -((x - true_x0) ** 2) / (2 * true_sigma**2)
    )

    res = fit_gaussian(x, y)

    assert isinstance(res, ModelResult)
    assert res.success is True
    assert res.best_values["center"] == pytest.approx(true_x0, abs=1e-2)
    assert res.best_values["sigma"] == pytest.approx(true_sigma, abs=1e-2)
    assert res.best_values["amplitude"] == pytest.approx(true_amplitude, abs=0.1)
    assert res.params["fwhm"].value == pytest.approx(true_fwhm, abs=1e-2)
    assert res.best_values["intercept"] == pytest.approx(true_baseline, abs=0.1)


def test_fit_gaussian_custom_guess_tuple() -> None:
    x0, sigma, amp, base = 5.0, 1.2, 80.0, 5.0
    x = np.linspace(0, 10, 101)
    y = base + (amp / (sigma * np.sqrt(2 * np.pi))) * np.exp(
        -((x - x0) ** 2) / (2 * sigma**2)
    )
    guess = (
        90.0,
        4.2,
        1.0,
        4.0,
        0.1,
        0.1,
    )
    res = fit_gaussian(x, y, guess)

    assert res.success is True
    assert res.best_values["intercept"] == pytest.approx(base, abs=1e-2)
    assert res.best_values["center"] == pytest.approx(5.0, abs=1e-2)
    assert res.best_values["sigma"] == pytest.approx(sigma, abs=1e-2)


def test_fit_gaussian_custom_guess_dict() -> None:
    x = np.linspace(0, 10, 101)
    y = 5.0 + 100.0 * np.exp(-((x - 4.5) ** 2) / (2 * 0.9**2))

    guess = {
        "amplitude": 90.0,
        "center": 4.2,
        "sigma": 1.0,
        "intercept": 0.1,
        "slope": 0.1,
    }
    res = fit_gaussian(x, y, guess=guess)

    assert res.success is True
    assert res.best_values["center"] == pytest.approx(4.5, abs=1e-2)
    assert res.best_values["sigma"] == pytest.approx(0.9, abs=0.1)


def test_fit_gaussian_noisy_data() -> None:
    np.random.seed(42)
    x = np.linspace(0, 20, 101)
    clean_y = 10.0 + 80.0 * np.exp(-((x - 10.0) ** 2) / (2 * 2.0**2))
    noise = np.random.normal(0, 1.5, size=x.shape)
    y = clean_y + noise

    res = fit_gaussian(x, y)
    assert res.success is True
    assert res.best_values["center"] == pytest.approx(10.0, abs=0.15)
    assert res.best_values["sigma"] == pytest.approx(2.0, abs=0.2)


def test_fit_gaussian_insufficient_points_raises() -> None:
    with pytest.raises(ValueError, match="4 data points are needed"):
        fit_gaussian([1.0, 2.0, 3.0], [10.0, 20.0, 10.0])


def test_fit_gaussian_dimension_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="x, y array must be same length"):
        fit_gaussian([1.0, 2.0, 3.0, 4.0], [1.0, 2.0, 3.0, 2.0, 3.0])


def test_calculate_com_symmetric_peak() -> None:
    x = np.linspace(-5, 5, 101)
    y = np.exp(-(x**2) / (2 * 1.0**2))
    com = calculate_com(x, y)
    assert com == pytest.approx(0.0, abs=1e-4)


def test_calculate_com_shifted_peak() -> None:
    x = np.linspace(0, 20, 201)
    y = 10.0 * np.exp(-((x - 7.5) ** 2) / (2 * 1.5**2))
    com = calculate_com(x, y)
    assert com == pytest.approx(7.5, abs=0.05)


def test_calculate_com_with_constant_background() -> None:
    x = np.linspace(0, 10, 101)
    y = 50.0 + 25.0 * np.exp(-((x - 4.0) ** 2) / (2 * 0.8**2))

    com_subtracted = calculate_com(x, y, subtract_baseline=True)
    assert com_subtracted == pytest.approx(4.0, abs=0.05)

    com_raw = calculate_com(x, y, subtract_baseline=False)
    assert abs(com_raw - 4.0) > abs(com_subtracted - 4.0)


def test_calculate_com_uneven_spacing() -> None:
    x = np.array([0.0, 1.0, 2.0, 5.0, 10.0])
    y = np.array([0.0, 10.0, 10.0, 0.0, 0.0])
    com = calculate_com(x, y, subtract_baseline=True)
    assert com == pytest.approx(1.5, abs=1e-4)


def test_calculate_com_flat_data_raises() -> None:
    x = np.linspace(0, 10, 20)
    y = np.full_like(x, 5.0)
    with pytest.raises(ValueError, match="Y is flat/Zero"):
        calculate_com(x, y)


def test_calculate_com_dimension_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="x, y array must be same length"):
        calculate_com([1.0, 2.0, 3.0], [1.0, 2.0])


def test_calculate_com_empty_raises() -> None:
    with pytest.raises(ValueError, match="At least 4 data points are needed"):
        calculate_com([], [])


def test_derivatives_polynomial() -> None:
    """Verify 1st and 2nd derivatives of y = x^2 (d1 = 2x, d2 = 2)."""
    x = np.linspace(-5, 5, 101)
    y = x**2

    res = calculate_derivatives(x, y)

    assert isinstance(res, DerivativeResult)
    assert res.d1[1:-1] == pytest.approx(2 * x[1:-1], abs=0.05)
    assert res.d2[2:-2] == pytest.approx(np.full_like(x[2:-2], 2.0), abs=0.05)
    assert any(zc == pytest.approx(0.0, abs=0.15) for zc in res.zero_crossings)


def test_derivatives_non_uniform_grid() -> None:
    """Verify derivatives on a non-uniform grid for y = 3x + 1 (d1 = 3, d2 = 0)."""
    x = np.array([0.0, 1.0, 3.0, 7.0, 15.0, 30.0])
    y = 3.0 * x + 1.0

    res = calculate_derivatives(x, y)
    assert res.d1 == pytest.approx(np.full_like(x, 3.0), abs=1e-3)
    assert res.d2 == pytest.approx(np.zeros_like(x), abs=1e-3)


def test_derivatives_insufficient_points_raises() -> None:
    with pytest.raises(ValueError, match="At least 4 data points are needed"):
        calculate_derivatives([1.0], [5.0])


def test_derivatives_dimension_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="x, y array must be same length"):
        calculate_derivatives([1.0, 2.0, 3.0], [1.0, 2.0])
