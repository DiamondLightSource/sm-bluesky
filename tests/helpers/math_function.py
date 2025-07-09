import numpy as np


def gaussian(x, mu, sig):
    return (
        1.0
        / (np.sqrt(2.0 * np.pi) * sig)
        * np.exp(-np.power((x - mu) / sig, 2.0) / 2.0)
    )


def step_function(x_data, step_centre):
    return [0.1 if x < step_centre else 1 for x in x_data]
