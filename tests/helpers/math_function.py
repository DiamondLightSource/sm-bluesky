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
    type: Callable,
    **arg,
) -> tuple[np.ndarray, np.ndarray]:
    x_data = np.linspace(start=start, stop=end, num=num, endpoint=True)
    y_data = type(
        **arg,
        x_data=x_data,
    )

    return y_data
