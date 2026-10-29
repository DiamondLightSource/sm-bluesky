import numpy as np
import pytest
from lmfit.model import ModelResult

from sm_bluesky.common.math.analysis import (
    calculate_com,
    fit_gaussian,
)


def test_fit_gaussian_clean_peak() -> None:
    """Fit a clean synthetic Gaussian peak and verify parameter recovery."""
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
    """Initial guess supplied as a tuple (amplitude, center, sigma, baseline)."""
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
    """Initial guess supplied as a dictionary."""
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
    """Fit a Gaussian with additive Gaussian noise."""
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
    """Fitting a 4-parameter model requires at least 4 data points."""
    with pytest.raises(ValueError, match="4 data points are needed"):
        fit_gaussian([1.0, 2.0, 3.0], [10.0, 20.0, 10.0])


def test_fit_gaussian_dimension_mismatch_raises() -> None:
    """Mismatched x and y lengths must raise ValueError."""
    with pytest.raises(ValueError, match="x, y array must be same length"):
        fit_gaussian([1.0, 2.0, 3.0, 4.0], [1.0, 2.0, 3.0, 2.0, 3.0])


def test_calculate_com_symmetric_peak() -> None:
    """A symmetric Gaussian peak centered at 0.0 should have COM at 0.0."""
    x = np.linspace(-5, 5, 101)
    y = np.exp(-(x**2) / (2 * 1.0**2))
    com = calculate_com(x, y)
    assert com == pytest.approx(0.0, abs=1e-4)


def test_calculate_com_shifted_peak() -> None:
    """A shifted Gaussian peak centered at 7.5 should have COM near 7.5."""
    x = np.linspace(0, 20, 201)
    y = 10.0 * np.exp(-((x - 7.5) ** 2) / (2 * 1.5**2))
    com = calculate_com(x, y)
    assert com == pytest.approx(7.5, abs=0.05)


def test_calculate_com_with_constant_background() -> None:
    """Baseline subtraction should correctly isolate the peak COM."""
    x = np.linspace(0, 10, 101)
    y = 50.0 + 25.0 * np.exp(-((x - 4.0) ** 2) / (2 * 0.8**2))

    com_subtracted = calculate_com(x, y, subtract_baseline=True)
    assert com_subtracted == pytest.approx(4.0, abs=0.05)

    com_raw = calculate_com(x, y, subtract_baseline=False)
    assert abs(com_raw - 4.0) > abs(com_subtracted - 4.0)


def test_calculate_com_uneven_spacing() -> None:
    """COM calculation should handle non-uniformly spaced coordinates."""
    x = np.array([0.0, 1.0, 2.0, 5.0, 10.0])
    y = np.array([0.0, 10.0, 10.0, 0.0, 0.0])
    com = calculate_com(x, y, subtract_baseline=True)
    assert com == pytest.approx(1.5, abs=1e-4)


def test_calculate_com_flat_data_raises() -> None:
    """Uniform flat data has no distinct COM and should raise ValueError."""
    x = np.linspace(0, 10, 20)
    y = np.full_like(x, 5.0)
    with pytest.raises(ValueError, match="Y is flat/Zero"):
        calculate_com(x, y)


def test_calculate_com_dimension_mismatch_raises() -> None:
    """Mismatched x and y lengths must raise ValueError."""
    with pytest.raises(ValueError, match="x, y array must be same length"):
        calculate_com([1.0, 2.0, 3.0], [1.0, 2.0])


def test_calculate_com_empty_raises() -> None:
    """Empty inputs must raise ValueError."""
    with pytest.raises(ValueError, match="At least 4 data points are needed"):
        calculate_com([], [])
