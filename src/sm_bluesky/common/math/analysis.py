"""Data analysis and fitting routines for scan data."""

from collections.abc import Sequence

import numpy as np
from lmfit.model import ModelResult
from lmfit.models import GaussianModel, LinearModel


def fit_gaussian(
    x: Sequence[float] | np.ndarray,
    y: Sequence[float] | np.ndarray,
    guess: tuple | dict[str, float] | None = None,
) -> ModelResult:
    """Fit a 1D Gaussian to (x, y) data.

    Model: y(x) = baseline + amplitude * exp(-(x - center)^2 / (2 * sigma^2))

    Parameters
    ----------
    x : Sequence[float] | np.ndarray
        Independent variable array.
    y : Sequence[float] | np.ndarray
        Dependent variable array.
    guess : tuple or dict, optional
        Initial parameter guess. If tuple: (amplitude, center, sigma, intercept,slope).
        If dict: keys {"amplitude", "center", "sigma", "baseline"}.
        If None, initial guesses are estimated automatically.

    Returns
    -------
    GaussianFitResult
        Result containing fitted parameters, COM, FWHM, and success flag.
    """
    if len(x) < 4 or len(y) < 4:
        raise ValueError("4 data points are needed")
    if len(x) != len(y):
        raise ValueError("x, y array must be same length")
    peak_0 = GaussianModel()
    line = LinearModel()
    model = peak_0 + line
    if not guess:
        params = peak_0.guess(data=y, x=x)
        params.update(line.guess(data=y, x=x))
    elif isinstance(guess, dict):
        params = model.make_params(**guess)
    else:
        amp, center, sigma, intercept = guess[:4]
        slope = guess[4] if len(guess) > 4 else 0.0
        params = model.make_params(
            amplitude=amp, center=center, sigma=sigma, intercept=intercept, slope=slope
        )
    output = model.fit(y, params=params, x=x)
    print(output.fit_report())
    return output
