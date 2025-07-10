from collections.abc import Callable
from dataclasses import dataclass

import numpy as np


def gaussian(x_data, centre, sig):
    return (
        1.0
        / (np.sqrt(2.0 * np.pi) * sig)
        * np.exp(-np.power((x_data - centre) / sig, 2.0) / 2.0)
    )


def step_function(x_data, centre):
    return [0.1 if x < centre else 1 for x in x_data]


@dataclass
class math_functions:
    gaussian: Callable = gaussian
    step_function: Callable = step_function


def generate_test_data(
    start: float,
    end: float,
    num: int,
    func: Callable,
    **arg,
) -> np.typing.NDArray[np.float64]:
    """
    Generate test data for a given mathematical function.

    Parameters
    ----------
    start : float
        Start value of the x-axis.
    end : float
        End value of the x-axis.
    num : int
        Number of points to generate.
    func : Callable
        The mathematical function to use for generating data.
    **arg
        Additional arguments to pass to the function.

    Returns
    -------
    np.typing.NDArray[np.float64]
        Array of generated y-values.
    """
    x_data = np.linspace(start=start, stop=end, num=num, endpoint=True)
    y_data = func(
        **arg,
        x_data=x_data,
    )
    y_data = np.array(y_data, dtype=np.float64)

    return y_data
