import numpy as np
import pytest

from sm_bluesky.common.math.grid_plotting import (
    binned_axis,
    edges_from_centres,
    extract_xyz,
    grid_heatmap,
    unique_axis,
)


@pytest.mark.parametrize(
    "centres, expected",
    [
        ([1.0], [0.5, 1.5]),
        ([0.0, 1.0, 2.0], [-0.5, 0.5, 1.5, 2.5]),
        ([0.0, 1.0, 3.0], [-0.5, 0.5, 2.0, 4.0]),
    ],
)
def test_edges_from_centres(centres: list[float], expected: list[float]) -> None:
    assert edges_from_centres(centres) == expected


def test_unique_axis():
    edges, indices = unique_axis([2.0, 0.0, 1.0, 0.0, 2.0])
    assert edges == [-0.5, 0.5, 1.5, 2.5]
    assert indices == [2, 0, 1, 0, 2]


@pytest.mark.parametrize(
    "values, n_bins, expected_edges, expected_indices",
    [
        ([0.0, 0.5, 1.0], 3, [-0.25, 0.25, 0.75, 1.25], [0, 1, 2]),
        ([5.0, 5.0], 1, [4.5, 5.5], [0, 0]),
    ],
)
def test_binned_axis(
    values: list[float],
    n_bins: int,
    expected_edges: list[float],
    expected_indices: list[int],
) -> None:
    edges, indices = binned_axis(values, n_bins=n_bins)
    assert edges == expected_edges
    assert indices == expected_indices


def test_extract_xyz_truncates_to_shortest_column():
    scan = {"x": [1, 2, 3, 4], "y": [10, 20, 30], "z": [5, 6]}
    assert extract_xyz(scan, "x", "y", "z") == ([1.0, 2.0], [10.0, 20.0], [5.0, 6.0])


def test_extract_xyz_drops_invalid_rows():
    scan = {
        "x": [1, 2, None, 4, 5],
        "y": [1, float("nan"), 3, 4, "bad"],
        "z": [1, 2, 3, float("inf"), 5],
    }
    assert extract_xyz(scan, "x", "y", "z") == ([1.0], [1.0], [1.0])


@pytest.mark.parametrize("missing", ["x", "y", "z", None])
def test_extract_xyz_missing_field_gives_empty(missing):
    scan = {"x": [1], "y": [1], "z": [1]}
    fields: dict[str, str | None] = {"x": "x", "y": "y", "z": "z"}
    if missing is None:
        fields["x"] = None
    else:
        fields[missing] = "not_there"
    assert extract_xyz(scan, fields["x"], fields["y"], fields["z"]) == ([], [], [])


def test_extract_xyz_keeps_snake_order():
    scan = {
        "x": [0, 1, 2, 2, 1, 0],
        "y": [0, 0, 0, 1, 1, 1],
        "z": [1, 2, 3, 4, 5, 6],
    }
    xs, ys, zs = extract_xyz(scan, "x", "y", "z")
    assert xs == [0.0, 1.0, 2.0, 2.0, 1.0, 0.0]
    assert zs == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]


def test_grid_heatmap_regular_grid():
    xs = [0.0, 1.0, 2.0] * 3
    ys = [5.0] * 3 + [10.0] * 3 + [15.0] * 3
    zs = [float(i) for i in range(9)]
    res = grid_heatmap(xs, ys, zs)
    assert res is not None
    x_edges, y_edges, grid = res
    assert x_edges == [-0.5, 0.5, 1.5, 2.5]
    assert y_edges == [2.5, 7.5, 12.5, 17.5]
    assert grid.shape == (3, 3)
    assert grid.tolist() == [[0, 1, 2], [3, 4, 5], [6, 7, 8]]


def test_grid_heatmap_uneven_steps_keep_real_positions():
    xs = [0.0, 1.0, 3.0] * 2
    ys = [0.0] * 3 + [2.0] * 3
    zs = [float(i) for i in range(6)]
    res = grid_heatmap(xs, ys, zs)
    assert res is not None
    x_edges, y_edges, grid = res
    assert x_edges == [-0.5, 0.5, 2.0, 4.0]
    assert y_edges == [-1.0, 1.0, 3.0]
    assert grid.shape == (2, 3)


def test_grid_heatmap_snake_order_places_points_by_position():
    xs = [0.0, 1, 2, 2, 1, 0]
    ys = [0.0, 0, 0, 1, 1, 1]
    zs = [1.0, 2, 3, 4, 5, 6]
    res = grid_heatmap(xs, ys, zs)
    assert res is not None
    _, _, grid = res
    assert grid.tolist() == [[1, 2, 3], [6, 5, 4]]


def test_grid_heatmap_incomplete_scan_masks_missing_cells():
    xs = [0.0, 1.0, 2.0] * 3
    ys = [0.0] * 3 + [1.0] * 3 + [2.0] * 3
    zs = [float(i) for i in range(9)]

    res = grid_heatmap(xs[:4], ys[:4], zs[:4])
    assert res is not None
    _, _, grid = res
    assert grid.shape == (2, 3)
    assert grid.count() == 4
    assert grid[1, 1] is np.ma.masked
    assert grid[1, 2] is np.ma.masked
    assert grid[0, 2] == 2
    assert grid[1, 0] == 3


def test_grid_heatmap_first_row_only():
    res = grid_heatmap([0.0, 1.0, 2.0], [5.0, 5.0, 5.0], [1.0, 2.0, 3.0])
    assert res is not None
    _, _, grid = res
    assert grid.shape == (1, 3)
    assert grid.tolist() == [[1, 2, 3]]


@pytest.mark.parametrize("fast_axis", ["x", "y"])
def test_grid_heatmap_bins_continuous_fast_axis(fast_axis: str) -> None:
    fast = [i * 0.8 + line * 0.08 for line in range(3) for i in range(10)]
    slow = [float(line) for line in range(3) for _ in range(10)]
    zs = [float(i) for i in range(30)]
    xs, ys = (fast, slow) if fast_axis == "x" else (slow, fast)

    res = grid_heatmap(xs, ys, zs)
    assert res is not None
    x_edges, y_edges, grid = res
    expected_shape = (3, 10) if fast_axis == "x" else (10, 3)
    assert grid.shape == expected_shape
    assert len(x_edges if fast_axis == "x" else y_edges) == 11
    assert grid.count() == 30


def test_grid_heatmap_single_point_and_empty():
    res = grid_heatmap([2.0], [3.0], [7.0])
    assert res is not None
    x_edges, y_edges, grid = res
    assert x_edges == [1.5, 2.5]
    assert y_edges == [2.5, 3.5]
    assert grid.tolist() == [[7.0]]
    assert grid_heatmap([], [], []) is None


def test_grid_heatmap_returns_none_when_not_on_a_grid():
    xs = [float(i) for i in range(10)]
    ys = [i * 0.38 for i in range(10)]
    assert grid_heatmap(xs, ys, xs) is None
