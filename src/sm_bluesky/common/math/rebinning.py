"""Math functions for rebinning"""

from collections import Counter
from typing import Any

import numpy as np

from .conversion import to_float


def extract_xyz(
    scan_data: dict[str, list[Any]],
    x_field: str | None,
    y_field: str | None,
    z_field: str | None,
) -> tuple[list[float], list[float], list[float]]:
    """Pull (x, y, z) out of a dictionary of data."""

    fields = (x_field, y_field, z_field)
    if any(f is None or f not in scan_data for f in fields):
        return [], [], []

    columns = [scan_data[f] for f in fields if f is not None]

    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []

    for rx, ry, rz in zip(*columns, strict=False):
        x = to_float(rx)
        y = to_float(ry)
        z = to_float(rz)
        if x is None or y is None or z is None:
            continue
        xs.append(x)
        ys.append(y)
        zs.append(z)

    return xs, ys, zs


def edges_from_centres(centres: list[float]) -> list[float]:
    """Cell edges halfway between nearest point centres."""
    if len(centres) == 1:
        return [centres[0] - 0.5, centres[0] + 0.5]
    first = centres[0] - (centres[1] - centres[0]) / 2
    last = centres[-1] + (centres[-1] - centres[-2]) / 2
    mids = [(a + b) / 2 for a, b in zip(centres[:-1], centres[1:], strict=True)]
    return [first, *mids, last]


def unique_axis(values: list[float]) -> tuple[list[float], list[int]]:
    """One cell per distinct position."""
    centres = sorted({round(v, 6) for v in values})
    index = {c: i for i, c in enumerate(centres)}
    return edges_from_centres(centres), [index[round(v, 6)] for v in values]


def binned_axis(values: list[float], n_bins: int) -> tuple[list[float], list[int]]:
    """Evenly spaced cells, for an axis that moves continuously (fast scans)."""
    lo, hi = min(values), max(values)
    step = (hi - lo) / (n_bins - 1) if n_bins > 1 else (hi - lo)
    if step <= 0:
        step = 1.0
    edges = [lo - step / 2 + k * step for k in range(n_bins + 1)]
    indices = [min(n_bins - 1, max(0, round((v - lo) / step))) for v in values]
    return edges, indices


def grid_heatmap(
    xs: list[float], ys: list[float], zs: list[float]
) -> tuple[list[float], list[float], Any] | None:
    """Bin scattered (x, y, z) points into a NxM matrix for pcolormesh to draw."""
    n_points = len(xs)
    if n_points == 0:
        return None

    n_unique_x = len({round(v, 6) for v in xs})
    n_unique_y = len({round(v, 6) for v in ys})
    max_unique = max(1, n_points // 2)
    x_is_grid = n_unique_x <= max_unique
    y_is_grid = n_unique_y <= max_unique

    if x_is_grid and y_is_grid:
        x_edges, x_idx = unique_axis(xs)
        y_edges, y_idx = unique_axis(ys)
    elif y_is_grid:
        row_length = max(Counter(round(v, 6) for v in ys).values())
        y_edges, y_idx = unique_axis(ys)
        x_edges, x_idx = binned_axis(xs, row_length)
    elif x_is_grid:
        row_length = max(Counter(round(v, 6) for v in xs).values())
        x_edges, x_idx = unique_axis(xs)
        y_edges, y_idx = binned_axis(ys, row_length)
    else:
        return None

    grid = np.full((len(y_edges) - 1, len(x_edges) - 1), np.nan)
    for xi, yi, z in zip(x_idx, y_idx, zs, strict=True):
        grid[yi, xi] = z
    return x_edges, y_edges, np.ma.masked_invalid(grid)
