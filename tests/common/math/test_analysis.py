import numpy as np
import pytest
from lmfit.model import ModelResult

from sm_bluesky.common.math.analysis import (
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
