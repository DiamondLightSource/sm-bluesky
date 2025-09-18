from typing import TypeVar

import numpy as np
from numpy import floating
from numpy.typing import NDArray

# Type variable for any floating dtype
DType = TypeVar("DType", bound=floating)


def gaussian(
    x: NDArray[DType],
    mu: float,
    sig: float,
) -> NDArray[DType]:
    return (
        1.0
        / (np.sqrt(2.0 * np.pi) * sig)
        * np.exp(-np.power((x - mu) / sig, 2.0) / 2.0)
    )
