"""Data analysis and fitting routines for scan data."""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from lmfit.model import ModelResult
from lmfit.models import GaussianModel, LinearModel
from numpy.typing import NDArray


@dataclass
class DerivativeResult:
    """Result of 1st and 2nd derivative calculations."""

    d1: NDArray[np.float64]
    d2: NDArray[np.float64]
    max_slope_x: float
    min_slope_x: float
    zero_crossings: list[float]


def _get_xy_ndarray(
    x: Sequence[float] | np.ndarray, y: Sequence[float] | np.ndarray
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    if len(x) != len(y):
        raise ValueError("x, y array must be same length")
    return np.asarray(x, dtype=float), np.asarray(y, dtype=float)


def calculate_com(
    x: Sequence[float] | np.ndarray,
    y: Sequence[float] | np.ndarray,
    subtract_baseline: bool = True,
) -> float:
    """Calculate Centre of Mass (COM) of 1D data.

    Parameters
    ----------
    x : Sequence[float] | np.ndarray
        Independent coordinate array.
    y : Sequence[float] | np.ndarray
        Dependent intensity/signal array.
    subtract_baseline : bool, optional
        Whether to subtract minimum value from y before calculation (default True).

    Returns
    -------
    float
        The calculated Centre of Mass along the x axis, or NaN if insufficient
        or flat data.
    """
    x_arr, y_arr = _get_xy_ndarray(x, y)
    if len(x_arr) < 2 or np.allclose(y_arr, y_arr[0]):
        return float("nan")

    if subtract_baseline:
        is_negative = (np.median(y_arr) - np.min(y_arr)) > (
            np.max(y_arr) - np.median(y_arr)
        )
        y_weight = np.max(y_arr) - y_arr if is_negative else y_arr - np.min(y_arr)
    else:
        y_weight = y_arr

    return float(np.average(x_arr, weights=y_weight))


def fit_gaussian(
    x: Sequence[float] | np.ndarray,
    y: Sequence[float] | np.ndarray,
    guess: tuple | dict[str, float] | None = None,
) -> ModelResult:
    """Fit a 1D Gaussian to (x, y) data.

    Model: y(x) = slope*x + intercept + amplitude * exp(-(x - centre)^2 / (2 * sigma^2))

    Parameters
    ----------
    x : Sequence[float] | np.ndarray
        Independent variable array.
    y : Sequence[float] | np.ndarray
        Dependent variable array.
    guess : tuple or dict, optional
        Initial parameter guess. If tuple: (amplitude, centre, sigma, intercept,slope).
        If dict: keys {"amplitude", "center", "sigma", , intercept, slope(optional)}.
        If None, initial guesses are estimated automatically.

    Returns
    -------
    ModelResult
        Result containing fitted parameters, COM, FWHM, and success flag.
    """
    x_arr, y_arr = _get_xy_ndarray(x, y)
    peak_0 = GaussianModel()
    line = LinearModel()
    model = peak_0 + line
    if len(x_arr) < 5 or np.allclose(y_arr, y_arr[0]):
        params = model.make_params(
            amplitude=np.nan,
            center=np.nan,
            sigma=np.nan,
            intercept=np.nan,
            slope=np.nan,
        )
        res = ModelResult(model, params)
        res.success = False
        res.best_fit = np.array([], dtype=float)
        res.best_values = params.valuesdict()
        return res
    if not guess:
        is_negative = bool(
            (np.median(y_arr) - np.min(y_arr)) > (np.max(y_arr) - np.median(y_arr))
        )
        n_bkg = max(2, len(y_arr) // 5)
        bkg_points = (
            np.argsort(y_arr)[-n_bkg:] if is_negative else np.argsort(y_arr)[:n_bkg]
        )
        line_params = line.guess(data=y_arr[bkg_points], x=x_arr[bkg_points])
        y_sub = y_arr - line.eval(line_params, x=x_arr)
        params = peak_0.guess(data=y_sub, x=x_arr, negative=is_negative)
        params.update(line_params)
    elif isinstance(guess, dict):
        params = model.make_params(False, **guess)
    else:
        amp, centre, sigma, intercept = guess[:4]
        slope = guess[4] if len(guess) > 4 else 0.0
        params = model.make_params(
            amplitude=amp, center=centre, sigma=sigma, intercept=intercept, slope=slope
        )
    output = model.fit(y_arr, params=params, x=x_arr)
    return output


def calculate_derivatives(
    x: Sequence[float] | np.ndarray,
    y: Sequence[float] | np.ndarray,
    log: bool = False,
) -> DerivativeResult:
    """Calculate 1st and 2nd derivatives of (x, y).

    Parameters
    ----------
    x : Sequence[float] | np.ndarray
        Independent variable array.
    y : Sequence[float] | np.ndarray
        Dependent variable array.
    log : bool, optional
        If True, take the natural logarithm of y before differentiating (default False).

    Returns
    -------
    DerivativeResult
        Contains d1 (dy/dx), d2 (d^2y/dx^2), edges and zero_crossings.
    """
    x_arr, y_arr = _get_xy_ndarray(x, y)
    if len(x_arr) < 3 or (log and np.any(y_arr <= 0)):
        return DerivativeResult(
            d1=np.array([], dtype=float),
            d2=np.array([], dtype=float),
            max_slope_x=float("nan"),
            min_slope_x=float("nan"),
            zero_crossings=[],
        )
    if log:
        y_arr = np.log(y_arr)
    d1 = np.gradient(y_arr, x_arr, edge_order=1)
    d2 = np.gradient(d1, x_arr, edge_order=2)
    max_slope_x = float(x_arr[np.argmax(d1)])
    min_slope_x = float(x_arr[np.argmin(d1)])
    zero_crossings = []
    for i, value in enumerate(d1[:-1]):
        if value == 0.0:
            zero_crossings.append(float(x_arr[i]))
        elif d1[i] * d1[i + 1] < 0:
            zero_crossings.append(float((x_arr[i] + x_arr[i + 1]) / 2.0))

    return DerivativeResult(
        d1=d1,
        d2=d2,
        max_slope_x=max_slope_x,
        min_slope_x=min_slope_x,
        zero_crossings=zero_crossings,
    )
