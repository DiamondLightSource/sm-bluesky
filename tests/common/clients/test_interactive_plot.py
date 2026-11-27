from unittest.mock import patch

import matplotlib.pyplot as plt
import numpy as np
import pytest
from matplotlib.collections import PathCollection, QuadMesh
from matplotlib.colors import LogNorm
from matplotlib.tri import TriContourSet

from sm_bluesky.common.clients.interactive_plot import (
    NO_FIELDS,
    InteractivePlotWindow,
    PlotMode,
)


@pytest.fixture
def sample_data():
    return {
        "scan1": {"Point number": [1, 2], "motor1": [0.1, 0.2], "det1": [10, 20]},
        "scan2": {"Point number": [1], "motor2": [0.5], "det1": [15]},
    }


@pytest.fixture(autouse=True)
def mock_show(monkeypatch):
    monkeypatch.setattr(plt, "show", lambda *args, **kwargs: None)
    monkeypatch.setattr(plt, "pause", lambda *args, **kwargs: None)


@pytest.fixture
def window(sample_data):
    return InteractivePlotWindow(sample_data, initial_scan_id="scan1")


def test_init(window: InteractivePlotWindow):
    assert "scan1" in window.active_scans
    assert len(window.scans) == 2
    assert "text_box" in window.widgets
    assert "unselect_btn" in window.widgets
    assert "scan_check" in window.widgets
    assert "radio_x" in window.widgets
    assert "check_y" in window.widgets


def test_get_active_fields(window: InteractivePlotWindow):
    fields = window.get_active_fields()
    assert "Point number" in fields
    assert "motor1" in fields
    assert "det1" in fields
    assert "motor2" not in fields


def test_get_visible_scans_shows_newest_window():
    large_data = {f"scan{i}": {"Point number": [1]} for i in range(15)}
    win = InteractivePlotWindow(large_data)
    assert win.get_visible_scans() == [f"scan{i}" for i in range(5, 15)]


def test_unselect_all(window: InteractivePlotWindow):
    window.unselect_all(None)
    assert len(window.active_scans) == 0


def test_submit_scan_valid(window: InteractivePlotWindow):
    window.active_scans.clear()
    window.submit_scan("scan2")
    assert "scan2" in window.active_scans


def test_submit_scan_invalid(window: InteractivePlotWindow):
    window.submit_scan("scan_missing")
    assert "scan_missing" not in window.active_scans


@pytest.mark.parametrize("text", ["", "Not found: 123"])
def test_submit_scan_empty_or_error(window: InteractivePlotWindow, text: str):
    initial_scans = set(window.active_scans)
    window.submit_scan(text)
    assert window.active_scans == initial_scans


def test_on_x_change(window: InteractivePlotWindow):
    with patch.object(window, "draw_plot") as mock_draw:
        window.on_x_change("motor1")
        mock_draw.assert_called_once()


@pytest.mark.parametrize("initial", [False, True])
def test_on_y_toggle_flips_state_and_redraws(
    window: InteractivePlotWindow, initial: bool
):
    window.active_y_states["det1"] = initial
    with patch.object(window, "draw_plot") as mock_draw:
        window.on_y_toggle("det1")
    assert window.active_y_states["det1"] is (not initial)
    mock_draw.assert_called_once()


def test_on_y_toggle_none_is_ignored(window: InteractivePlotWindow):
    before = dict(window.active_y_states)
    window.on_y_toggle(None)
    assert window.active_y_states == before


@pytest.mark.parametrize("initially_active", [False, True])
def test_on_scan_toggle(window: InteractivePlotWindow, initially_active: bool):
    window.active_scans.clear()
    if initially_active:
        window.active_scans.add("scan2")
    window.on_scan_toggle("scan2")
    assert ("scan2" in window.active_scans) is (not initially_active)


def test_on_scan_toggle_none_is_ignored(window: InteractivePlotWindow):
    before = set(window.active_scans)
    window.on_scan_toggle(None)
    assert window.active_scans == before


def test_update_plot_new_scan_rebuilds_ui(window: InteractivePlotWindow):
    window.data_source["scan3"] = {"Point number": [1]}
    with (
        patch.object(window, "build_ui") as mock_build,
        patch.object(window, "draw_plot") as mock_draw,
    ):
        window.update_plot()
    mock_build.assert_called_once()
    mock_draw.assert_called_once()
    assert "scan3" in window.scans
    assert "scan3" in window.active_scans


def test_update_plot_new_point_redraws_without_rebuild(
    window: InteractivePlotWindow,
):
    window.data_source["scan3"] = {"Point number": [1]}
    window.update_plot()
    window.data_source["scan3"]["Point number"].append(2)
    with (
        patch.object(window, "build_ui") as mock_build,
        patch.object(window, "draw_plot") as mock_draw,
    ):
        window.update_plot()
    mock_build.assert_not_called()
    mock_draw.assert_called_once()


def test_update_plot_closed(window: InteractivePlotWindow):
    plt.close(window.fig)
    with patch.object(window, "draw_plot") as mock_draw:
        window.update_plot()
        mock_draw.assert_not_called()


def test_draw_with_x_choice(window: InteractivePlotWindow):
    with patch.object(window.ax, "set_xlabel") as mock_xlabel:
        window.on_x_change("motor1")
        mock_xlabel.assert_called_with("motor1")


def test_build_ui_explicitly(window: InteractivePlotWindow):
    window.data_source["scan1"]["brand_new_motor"] = [5, 10]
    assert "brand_new_motor" not in window.active_y_states
    window.build_ui()
    assert "brand_new_motor" in window.active_y_states


def test_draw_plot_explicitly(window: InteractivePlotWindow):
    window.active_y_states["det1"] = True
    window.active_scans.add("scan1")
    window.draw_plot()
    assert len(window.ax.lines) > 0


def test_draw_plot_x_axis_fallback(window: InteractivePlotWindow):
    window.line_x = "motor1"
    window.active_scans.add("scan1")
    window.active_scans.add("scan2")
    with patch.object(window.ax, "set_xlabel") as mock_xlabel:
        window.draw_plot()
        mock_xlabel.assert_called_with("Point number")


@pytest.fixture
def grid_data():
    xs = [0.0, 1.0, 2.0] * 3
    ys = [0.0] * 3 + [1.0] * 3 + [2.0] * 3
    return {
        "grid": {
            "x_motor": xs,
            "y_motor": ys,
            "det": [float(i) for i in range(9)],
        },
        "other": {"x_motor": [0.0], "y_motor": [0.0], "det": [1.0]},
    }


@pytest.fixture
def grid_window(grid_data):
    win = InteractivePlotWindow(grid_data, initial_scan_id="grid")
    win.on_mode_change(PlotMode.GRID_2D)
    return win


def test_mode_defaults_to_1d(window: InteractivePlotWindow):
    assert window.mode == PlotMode.LINE_1D
    assert "mode_radio" in window.widgets
    assert not window.ax_cbar.get_visible()
    assert not window.ax_z.get_visible()


@pytest.mark.parametrize("mode", [PlotMode.GRID_2D, PlotMode.CONTOUR_2D])
def test_switch_to_2d_mode_builds_2d_controls(grid_data, mode: PlotMode):
    win = InteractivePlotWindow(grid_data, initial_scan_id="grid")
    win.on_mode_change(mode)
    assert win.mode == mode
    assert {"radio_x", "radio_y", "radio_z"} <= win.widgets.keys()
    assert "check_y" not in win.widgets
    assert win.ax_z.get_visible()
    assert win.ax_cbar.get_visible()
    assert (win.x_field, win.y_field, win.z_field) == ("x_motor", "y_motor", "det")


def _filled_cells(win) -> int:
    mesh = win.ax.collections[0]
    return int(np.ma.masked_invalid(mesh.get_array()).count())


def test_2d_draw_heatmap_with_colorbar(grid_window: InteractivePlotWindow):
    win = grid_window
    assert len(win.ax.collections) == 1
    assert isinstance(win.ax.collections[0], QuadMesh)
    assert _filled_cells(win) == 9
    assert win.ax.get_xlabel() == "x_motor"
    assert win.ax.get_ylabel() == "y_motor"
    assert win.ax_cbar.get_ylabel() == "det"
    assert win.ax.collections[0].get_cmap().name == "viridis"


def test_2d_falls_back_to_scatter_when_not_on_a_grid(
    grid_window: InteractivePlotWindow,
):
    win = grid_window
    scan = win.data_source["grid"]
    scan["x_motor"] = [float(i) for i in range(10)]
    scan["y_motor"] = [i * 0.37 for i in range(10)]
    scan["det"] = [float(i) for i in range(10)]
    win.draw_plot()
    assert not isinstance(win.ax.collections[0], QuadMesh)
    assert len(np.asarray(win.ax.collections[0].get_offsets())) == 10
    assert win.ax_cbar.get_visible()


def test_2d_selection_changes_update_state_and_plot(grid_window: InteractivePlotWindow):
    win = grid_window
    win.on_x_change("y_motor")
    win.on_y_change("x_motor")
    win.on_z_change("x_motor")
    assert (win.x_field, win.y_field, win.z_field) == ("y_motor", "x_motor", "x_motor")
    assert win.ax.get_xlabel() == "y_motor"
    assert win.ax.get_ylabel() == "x_motor"
    assert win.ax_cbar.get_ylabel() == "x_motor"


def test_2d_selection_survives_ui_rebuild(grid_window: InteractivePlotWindow):
    win = grid_window
    win.on_z_change("y_motor")
    win.build_ui()
    assert win.z_field == "y_motor"
    assert win.widgets["radio_z"].value_selected == "y_motor"


def test_2d_ignores_placeholder_and_none_labels(grid_window: InteractivePlotWindow):
    win = grid_window
    win.on_x_change(None)
    win.on_y_change(None)
    win.on_z_change(None)
    win.on_y_change(NO_FIELDS)
    win.on_z_change(NO_FIELDS)
    assert (win.x_field, win.y_field, win.z_field) == ("x_motor", "y_motor", "det")


def test_2d_uses_most_recent_active_scan(grid_window: InteractivePlotWindow):
    win = grid_window
    assert win.get_2d_scan() == "grid"
    win.active_scans.add("other")
    assert win.get_2d_scan() == "other"
    win.build_ui()
    win.draw_plot()
    assert _filled_cells(win) == 1
    assert "Scan other" in win.ax.get_title(loc="left")


@pytest.mark.parametrize("mode", [PlotMode.GRID_2D, PlotMode.CONTOUR_2D])
def test_2d_no_scan_selected(grid_data, mode: PlotMode):
    win = InteractivePlotWindow(grid_data, initial_scan_id="grid")
    win.on_mode_change(mode)
    win.unselect_all(None)
    assert win.get_2d_scan() is None
    assert win.get_2d_fields() == []
    assert len(win.ax.collections) == 0
    assert "no scan selected" in win.ax.get_title(loc="left")
    assert (win.x_field, win.y_field, win.z_field) == (None, None, None)


@pytest.mark.parametrize("mode", [PlotMode.GRID_2D, PlotMode.CONTOUR_2D])
def test_2d_waiting_for_data(grid_data, mode: PlotMode):
    grid_data["grid"] = {"x_motor": [], "y_motor": [], "det": []}
    win = InteractivePlotWindow(grid_data, initial_scan_id="grid")
    win.on_mode_change(mode)
    assert len(win.ax.collections) == 0
    assert "waiting for data" in win.ax.get_title(loc="left")
    assert not win.ax_cbar.get_visible()


def test_2d_incomplete_rows_and_mismatched_columns(grid_window: InteractivePlotWindow):
    win = grid_window
    win.data_source["grid"]["det"] = [1.0, 2.0, 3.0, 4.0]
    win.draw_plot()
    assert _filled_cells(win) == 4


def test_2d_update_plot_picks_up_new_points(grid_window: InteractivePlotWindow):
    win = grid_window
    win.update_plot()
    n_before = _filled_cells(win)
    for column in win.data_source["grid"].values():
        column.append(9.0)
    win.update_plot()
    assert _filled_cells(win) == n_before + 1


def test_2d_redraw_reuses_single_colorbar_axes(grid_window: InteractivePlotWindow):
    win = grid_window
    n_axes = len(win.fig.axes)
    for _ in range(3):
        win.draw_plot()
    assert len(win.fig.axes) == n_axes


def test_switch_back_to_1d_restores_1d_controls(grid_window: InteractivePlotWindow):
    win = grid_window
    win.on_mode_change(PlotMode.LINE_1D)
    assert win.mode == PlotMode.LINE_1D
    assert "check_y" in win.widgets
    assert "radio_y" not in win.widgets
    assert "radio_z" not in win.widgets
    assert not win.ax_cbar.get_visible()
    assert not win.ax_z.get_visible()
    assert "Point number" in [t.get_text() for t in win.widgets["radio_x"].labels]


def test_on_mode_change_ignores_unknown_and_same_mode(
    grid_window: InteractivePlotWindow,
):
    win = grid_window
    with patch.object(win, "build_ui") as mock_build:
        win.on_mode_change(PlotMode.GRID_2D)
        win.on_mode_change("junk")
        win.on_mode_change(None)
        mock_build.assert_not_called()


def test_1d_x_change_does_not_touch_2d_state(window: InteractivePlotWindow):
    window.on_x_change("motor1")
    assert window.x_field is None


def test_2d_single_field_scan_defaults(grid_data):
    grid_data["grid"] = {"only": [1.0, 2.0]}
    win = InteractivePlotWindow(grid_data, initial_scan_id="grid")
    win.on_mode_change(PlotMode.GRID_2D)
    assert (win.x_field, win.y_field, win.z_field) == ("only", "only", "only")


def test_contour_draw_with_colorbar(grid_data):
    win = InteractivePlotWindow(grid_data, initial_scan_id="grid")
    win.on_mode_change(PlotMode.CONTOUR_2D)
    assert win.ax_cbar.get_visible()
    assert win.ax.get_xlabel() == "x_motor"
    assert win.ax.get_ylabel() == "y_motor"
    assert win.ax_cbar.get_ylabel() == "det"
    assert isinstance(win.ax.collections[0], TriContourSet)


@pytest.mark.parametrize("log_scale", [False, True])
def test_contour_draw_fallback_collinear(grid_data, log_scale: bool):
    grid_data["grid"] = {
        "x_motor": [0.0, 1.0, 2.0],
        "y_motor": [0.0, 0.0, 0.0],
        "det": [1.0, 2.0, 3.0],
    }
    win = InteractivePlotWindow(grid_data, initial_scan_id="grid")
    win.on_mode_change(PlotMode.CONTOUR_2D)
    if log_scale:
        win.on_log_toggle("Log Scale")
    assert win.ax_cbar.get_visible()
    assert isinstance(win.ax.collections[0], PathCollection)
    assert isinstance(win.ax.collections[0].norm, LogNorm) is log_scale


def test_log_scale_default_false(window: InteractivePlotWindow):
    assert window.log_scale is False
    assert "check_log" in window.widgets


@pytest.mark.parametrize("initial", [False, True])
def test_on_log_toggle_flips_and_redraws(window: InteractivePlotWindow, initial):
    window.log_scale = initial
    with patch.object(window, "draw_plot") as mock_draw:
        window.on_log_toggle("Log Scale")
    assert window.log_scale is (not initial)
    mock_draw.assert_called_once()


def test_on_log_toggle_ignores_other_labels(window: InteractivePlotWindow):
    window.on_log_toggle("Other")
    assert window.log_scale is False


@pytest.mark.parametrize(
    "n_toggles, expected", [(0, "linear"), (1, "log"), (2, "linear")]
)
def test_1d_log_scale(window: InteractivePlotWindow, n_toggles: int, expected: str):
    for _ in range(n_toggles):
        window.on_log_toggle("Log Scale")
    assert window.ax.get_yscale() == expected


def test_1d_log_scale_non_positive():
    data = {"1": {"y1": [-5, 0], "y2": [-1, -2]}}
    win = InteractivePlotWindow(data, initial_scan_id="1")
    win.on_log_toggle("Log Scale")
    assert win.ax.get_yscale() == "linear"


@pytest.mark.parametrize(
    "mode, collection_type",
    [(PlotMode.GRID_2D, QuadMesh), (PlotMode.CONTOUR_2D, TriContourSet)],
)
def test_2d_log_scale(grid_data, mode: PlotMode, collection_type: type):
    win = InteractivePlotWindow(grid_data, initial_scan_id="grid")
    win.on_mode_change(mode)
    win.on_log_toggle("Log Scale")
    mappable = win.ax.collections[0]
    assert isinstance(mappable, collection_type)
    assert isinstance(mappable.norm, LogNorm)
    assert win.ax_cbar.get_visible()


def test_2d_log_scale_non_positive():
    data = {
        "grid": {
            "x": [0, 1, 0, 1],
            "y": [0, 0, 1, 1],
            "det": [0.0, -1.0, -2.0, 0.0],
        }
    }
    win = InteractivePlotWindow(data, initial_scan_id="grid")
    win.on_mode_change(PlotMode.GRID_2D)
    win.on_log_toggle("Log Scale")
    assert win._get_2d_norm([0.0, -1.0, -2.0]) is None
    mappable = win.ax.collections[0]
    assert not isinstance(mappable.norm, LogNorm)


def test_2d_log_scale_uniform_positive():
    data = {
        "grid": {
            "x": [0, 1, 0, 1],
            "y": [0, 0, 1, 1],
            "det": [10.0, 10.0, 10.0, 10.0],
        }
    }
    win = InteractivePlotWindow(data, initial_scan_id="grid")
    win.on_mode_change(PlotMode.GRID_2D)
    win.on_log_toggle("Log Scale")
    norm = win.ax.collections[0].norm
    assert isinstance(norm, LogNorm)
    assert norm.vmin == pytest.approx(9.0)
    assert norm.vmax == pytest.approx(11.0)


def test_log_scale_persists_across_mode_changes(grid_data):
    win = InteractivePlotWindow(grid_data, initial_scan_id="grid")
    win.on_log_toggle("Log Scale")
    assert win.log_scale is True
    win.on_mode_change(PlotMode.GRID_2D)
    assert win.log_scale is True
    assert isinstance(win.ax.collections[0].norm, LogNorm)
    win.on_mode_change(PlotMode.LINE_1D)
    assert win.log_scale is True
    assert win.ax.get_yscale() == "log"


def test_2d_log_scale_contour_single_decade():
    data = {
        "scan": {
            "x": [0, 1, 2, 0, 1, 2, 0, 1, 2],
            "y": [0, 0, 0, 1, 1, 1, 2, 2, 2],
            "det": [1e8, 2e8, 3e8, 4e8, 5e8, 6e8, 7e8, 8e8, 9e8],
        }
    }
    win = InteractivePlotWindow(data, initial_scan_id="scan")
    win.on_mode_change(PlotMode.CONTOUR_2D)
    win.on_log_toggle("Log Scale")
    assert win.log_scale is True
    assert isinstance(win.ax.collections[0], TriContourSet)
    assert isinstance(win.ax.collections[0].norm, LogNorm)


@pytest.mark.parametrize("log_scale", [False, True])
def test_2d_contour_large_z_overflow(log_scale: bool):
    """z values beyond 32-bit range must not raise OverflowError; the contour
    plot is still drawn."""
    data = {
        "scan": {
            "x": [0, 1, 2, 0, 1, 2, 0, 1, 2],
            "y": [0, 0, 0, 1, 1, 1, 2, 2, 2],
            "det": [1e8, 5e8, 4.5e9, 2e8, 3e9, 1e9, 4e8, 2.5e9, 3.5e19],
        }
    }
    win = InteractivePlotWindow(data, initial_scan_id="scan")
    win.on_mode_change(PlotMode.CONTOUR_2D)
    if log_scale:
        win.on_log_toggle("Log Scale")
    assert isinstance(win.ax.collections[0], TriContourSet)


def test_custom_cmap(grid_data):
    win = InteractivePlotWindow(grid_data, initial_scan_id="grid", cmap="plasma")
    win.on_mode_change(PlotMode.GRID_2D)
    assert win.cmap == "plasma"
    assert win.ax.collections[0].get_cmap().name == "plasma"


def test_invalid_cmap_fallback(grid_data):
    with patch("click.secho") as mock_secho:
        win_bad = InteractivePlotWindow(
            grid_data, initial_scan_id="grid", cmap="not_a_colormap"
        )
        assert win_bad.cmap == "viridis"
        mock_secho.assert_called_once_with(
            "Unknown colormap 'not_a_colormap', falling back to 'viridis'.",
            fg="yellow",
        )


def test_analysis_fields_filtered_in_1d_and_2d():
    data = {
        "scan1": {
            "pgm-energy": [1.0, 2.0, 3.0, 4.0],
            "det1": [10.0, 50.0, 20.0, 5.0],
            "gaussian": [11.0, 48.0, 21.0, 6.0],
            "d1": [40.0, 5.0, -22.5, -15.0],
            "d2": [-35.0, -31.25, -10.0, 7.5],
            "centre": [2.2],
            "com": [2.3],
            "zero_crossing": [2.2],
            "max_slope_x": [1.0],
            "min_slope_x": [3.0],
        }
    }
    win = InteractivePlotWindow(data, initial_scan_id="scan1")

    active_fields = win.get_active_fields()
    assert active_fields == ["det1", "pgm-energy", "gaussian", "d1", "d2"]
    assert win.active_y_states["det1"] is True
    assert win.active_y_states["gaussian"] is False

    x_labels = [t.get_text() for t in win.widgets["radio_x"].labels]
    assert x_labels == ["Point number", "det1", "pgm-energy"]
    assert win.get_2d_fields() == ["pgm-energy", "det1"]


@pytest.mark.parametrize(
    "removed, expected_active",
    [
        (["scan2"], {"scan1"}),
        (["scan1"], {"scan2"}),
    ],
)
def test_update_plot_resyncs_when_scans_removed(
    window: InteractivePlotWindow, removed: list[str], expected_active: set[str]
):
    for scan_id in removed:
        del window.data_source[scan_id]
    window.update_plot()
    assert window.active_scans == expected_active


def test_update_plot_resync_tracks_remaining_scans(window: InteractivePlotWindow):
    del window.data_source["scan1"]
    window.data_source["scan9"] = {"Point number": [1]}
    window.update_plot()
    assert window.scans == ["scan2", "scan9"]


def test_update_plot_resync_after_all_scans_removed(window: InteractivePlotWindow):
    window.data_source.clear()
    window.update_plot()
    assert (window.scans, window.active_scans) == ([], set())


def test_update_plot_selects_scans_added_with_replacement(
    window: InteractivePlotWindow,
):
    window.active_scans = {"scan2"}
    window.data_source["scan2"] = {"Point number": [1]}
    window.data_source["scan3"] = {"Point number": [1]}
    window.update_plot()
    assert window.active_scans == {"scan2", "scan3"}


def test_update_plot_keeps_unreplaced_selection(window: InteractivePlotWindow):
    window.active_scans = {"scan1"}
    window.data_source["scan2"] = {"Point number": [5]}
    window.update_plot()
    assert "scan1" in window.active_scans


@pytest.mark.parametrize(
    "action",
    [
        lambda w: w.on_log_toggle("Log Scale"),
        lambda w: w.on_mode_change(PlotMode.GRID_2D),
        lambda w: w.on_y_toggle("det1"),
        lambda w: w.draw_plot(),
        lambda w: w.build_ui(),
    ],
    ids=["log", "mode", "y-toggle", "draw", "build"],
)
def test_ui_callbacks_survive_scan_removed_before_update(
    window: InteractivePlotWindow, action
):
    del window.data_source["scan1"]
    action(window)
    assert "scan1" not in window.active_scans


@pytest.fixture
def live_2d_window(grid_data):
    """2D window on 'grid' with a new, still empty scan 'live' just started."""
    win = InteractivePlotWindow(grid_data, initial_scan_id="grid")
    win.on_mode_change(PlotMode.GRID_2D)
    win.on_x_change("y_motor")
    win.on_y_change("x_motor")
    grid_data["live"] = {}
    win.update_plot()
    return win, grid_data["live"]


def _add_points(scan: dict, n: int) -> None:
    for i in range(n):
        for key, value in (("x_motor", i % 2), ("y_motor", i // 2), ("det", i)):
            scan.setdefault(key, []).append(float(value))


def test_2d_new_scan_draws_once_data_arrives(live_2d_window):
    win, live = live_2d_window
    _add_points(live, 4)
    win.update_plot()
    assert "waiting for data" not in win.ax.get_title(loc="left")


def test_2d_new_scan_keeps_user_axis_choice(live_2d_window):
    win, live = live_2d_window
    _add_points(live, 4)
    win.update_plot()
    assert (win.x_field, win.y_field) == ("y_motor", "x_motor")


@pytest.mark.parametrize(
    "values",
    [[None, 1.0, 2.0], ["on", 1.0, 2.0], [None, None, None], [np.nan, 3.0, 1.0]],
    ids=["none", "string", "all-none", "nan"],
)
def test_1d_log_scale_tolerates_non_numeric(values):
    data = {"1": {"y": values}}
    win = InteractivePlotWindow(data, initial_scan_id="1")
    win.on_log_toggle("Log Scale")
    expected = (
        "log" if any(isinstance(v, float) and v > 0 for v in values) else ("linear")
    )
    assert win.ax.get_yscale() == expected


# --- Look and feel / UX --------------------------------------------------------


@pytest.fixture
def fit_window():
    """1D window over three peak scans; scan 'c' carries fit results."""
    x = [float(v) for v in np.linspace(-2, 2, 21)]
    data = {}
    for name, centre in (("a", 0.0), ("b", 0.5), ("c", -0.5)):
        y = [float(100 * np.exp(-((v - centre) ** 2) / 0.3)) for v in x]
        data[name] = {"energy": x, "det": y}
    data["c"]["gaussian"] = list(data["c"]["det"])
    data["c"]["centre"] = [-0.5]
    data["c"]["d1"] = [float(v) for v in np.gradient(data["c"]["det"], x)]
    win = InteractivePlotWindow(data, initial_scan_id="a")
    win.active_scans |= {"b", "c"}
    win.build_ui()
    _choose_x(win, "energy")
    return win


def _choose_x(win: InteractivePlotWindow, field: str) -> None:
    radio = win.widgets["radio_x"]
    radio.set_active([t.get_text() for t in radio.labels].index(field))


def _legend_labels(win: InteractivePlotWindow) -> list[str]:
    legend = win.ax.get_legend()
    return [t.get_text() for t in legend.get_texts()] if legend else []


def test_scan_colour_stable_when_other_scans_toggle(fit_window):
    before = fit_window.scan_colour("c")
    fit_window.on_scan_toggle("a")
    assert fit_window.scan_colour("c") == before


def test_scan_lines_use_scan_colour(fit_window):
    colours = {
        line.get_label(): line.get_color()
        for line in fit_window.ax.lines
        if line.get_label().endswith(": det")
    }
    assert colours == {f"{s}: det": fit_window.scan_colour(s) for s in ("a", "b", "c")}


def test_legend_ordered_by_scan(fit_window):
    assert _legend_labels(fit_window) == ["a: det", "b: det", "c: det"]


def test_scan_list_labels_coloured_like_lines(fit_window):
    labels = fit_window.widgets["scan_check"].labels
    assert [t.get_color() for t in labels] == [
        fit_window.scan_colour(t.get_text()) for t in labels
    ]


def test_fit_gaussian_drawn_dashed(fit_window):
    fit_window.on_y_toggle("gaussian")
    (line,) = [ln for ln in fit_window.ax.lines if ln.get_label() == "c: gaussian"]
    assert line.get_linestyle() == "--"


def test_fit_centre_marked_when_x_is_a_real_axis(fit_window):
    fit_window.on_y_toggle("gaussian")
    assert [t.get_text() for t in fit_window.ax.texts] == ["-0.5"]


def test_fit_centre_not_marked_against_point_number(fit_window):
    _choose_x(fit_window, "Point number")
    fit_window.on_y_toggle("gaussian")
    assert len(fit_window.ax.texts) == 0


def test_derivative_drawn_on_right_hand_axis(fit_window):
    fit_window.on_y_toggle("d1")
    assert [ln.get_label() for ln in fit_window.ax_d.lines] == ["c: d1"]


def test_derivative_axis_label_on_right(fit_window):
    fit_window.on_y_toggle("d1")
    assert fit_window.ax_d.yaxis.get_label_position() == "right"


@pytest.mark.parametrize("toggle_d1", [False, True])
def test_derivative_axis_shown_only_with_derivatives(fit_window, toggle_d1: bool):
    if toggle_d1:
        fit_window.on_y_toggle("d1")
    assert fit_window.ax_d.get_visible() is toggle_d1


def test_derivatives_not_on_main_axis(fit_window):
    fit_window.on_y_toggle("d1")
    assert all("d1" not in ln.get_label() for ln in fit_window.ax.lines)


@pytest.mark.parametrize("n_points, has_markers", [(10, True), (60, True), (61, False)])
def test_markers_only_for_short_scans(n_points: int, has_markers: bool):
    data = {"s": {"det": [float(i) for i in range(n_points)]}}
    win = InteractivePlotWindow(data)
    assert (win.ax.lines[0].get_marker() not in (None, "None", "")) is has_markers


def test_non_numeric_readings_plotted_as_gaps():
    data = {"s": {"x": [1.0, 2.0, 3.0], "det": [1.0, "bad", 3.0]}}
    win = InteractivePlotWindow(data)
    assert np.isnan(win.ax.lines[0].get_ydata()[1])


@pytest.mark.parametrize(
    "scans, expected",
    [
        (["a"], "Scan a  ·  det"),
        (["a", "b", "c"], "Scans a, b, c  ·  det"),
    ],
)
def test_1d_title_names_scans_and_channels(fit_window, scans, expected):
    fit_window.active_scans = set(scans)
    fit_window.draw_plot()
    assert fit_window.ax.get_title(loc="left") == expected


def test_status_line_summarises_newest_scan(fit_window):
    assert fit_window._status_text.get_text().startswith(
        "Scan c: 21 points   ·   3 scans shown"
    )


@pytest.mark.parametrize(
    "setup, hint",
    [
        (lambda w: w.unselect_all(None), "Select a scan on the right to plot it."),
        (lambda w: w.on_y_toggle("det"), "Tick a Y channel to plot it."),
    ],
    ids=["no-scan", "no-channel"],
)
def test_empty_plot_shows_hint(fit_window, setup, hint: str):
    setup(fit_window)
    assert [t.get_text() for t in fit_window.ax.texts] == [hint]


def test_select_latest_keeps_only_newest(fit_window):
    fit_window.select_latest(None)
    assert fit_window.active_scans == {"c"}


@pytest.mark.parametrize("follow, expected", [(False, {"a", "new"}), (True, {"new"})])
def test_follow_latest_controls_new_scan_selection(
    sample_data, follow: bool, expected: set[str]
):
    sample_data.clear()
    sample_data["a"] = {"Point number": [1]}
    win = InteractivePlotWindow(sample_data, initial_scan_id="a")
    win.follow_latest = follow
    sample_data["new"] = {"Point number": [1]}
    win.update_plot()
    assert win.active_scans == expected


def test_follow_latest_option_selects_newest(fit_window):
    fit_window.on_option_toggle("Follow Latest")
    assert (fit_window.follow_latest, fit_window.active_scans) == (True, {"c"})


def test_log_option_routed_from_options_box(fit_window):
    fit_window.on_option_toggle("Log Scale")
    assert fit_window.log_scale is True


def _key(win: InteractivePlotWindow, key: str) -> None:
    from matplotlib.backend_bases import KeyEvent

    win.on_key(KeyEvent("key_press_event", win.fig.canvas, key))


def test_key_l_toggles_log_and_checkbox(fit_window):
    _key(fit_window, "l")
    assert fit_window.log_scale is True
    assert fit_window.widgets["check_log"].get_status()[0] is True


@pytest.mark.parametrize(
    "presses, expected",
    [(1, PlotMode.GRID_2D), (2, PlotMode.CONTOUR_2D), (3, PlotMode.LINE_1D)],
)
def test_key_m_cycles_mode(fit_window, presses: int, expected: PlotMode):
    for _ in range(presses):
        _key(fit_window, "m")
    assert fit_window.mode == expected


def test_mode_change_syncs_mode_radio(fit_window):
    fit_window.on_mode_change(PlotMode.CONTOUR_2D)
    assert fit_window.widgets["mode_radio"].value_selected == PlotMode.CONTOUR_2D


@pytest.mark.parametrize("key, expected", [("n", {"c"}), ("u", set())])
def test_selection_keys(fit_window, key: str, expected: set[str]):
    _key(fit_window, key)
    assert fit_window.active_scans == expected


def test_other_keys_go_to_matplotlib(fit_window):
    with patch(
        "sm_bluesky.common.clients.interactive_plot.key_press_handler"
    ) as default:
        _key(fit_window, "g")
    default.assert_called_once()


def test_2d_marks_newest_point(grid_window: InteractivePlotWindow):
    (marker,) = grid_window.ax.lines
    assert (marker.get_xdata()[0], marker.get_ydata()[0]) == (2.0, 2.0)


@pytest.mark.parametrize("n_fields", [3, 12, 40])
def test_controls_stay_inside_panel(n_fields: int):
    data = {"s": {f"ch{i:02d}": [1.0, 2.0] for i in range(n_fields)}}
    win = InteractivePlotWindow(data)
    bottoms = [
        ax.get_position().y0
        for ax in (win.ax_scan_txt, win.ax_scan, win.ax_mode, win.ax_x, win.ax_y)
    ]
    assert min(bottoms) >= 0.05


# --- Scrollable scan list -----------------------------------------------------


@pytest.fixture
def many_scans():
    return {f"s{i:02d}": {"det": [float(i), float(i + 1)]} for i in range(25)}


@pytest.fixture
def long_list(many_scans):
    return InteractivePlotWindow(many_scans, initial_scan_id="s24")


def _shown(win: InteractivePlotWindow) -> list[str]:
    return [t.get_text() for t in win.widgets["scan_check"].labels]


def test_scan_list_starts_at_newest(long_list):
    assert _shown(long_list) == [f"s{i:02d}" for i in range(15, 25)]


@pytest.mark.parametrize(
    "rows, first",
    [(-1, 14), (-5, 10), (-100, 0), (100, 15), (0, 15)],
)
def test_scroll_scans_moves_window_and_clamps(long_list, rows: int, first: int):
    long_list.scroll_scans(rows)
    assert _shown(long_list)[0] == f"s{first:02d}"


def test_scrolled_away_scans_stay_selected(long_list):
    long_list.scroll_scans(-100)
    assert "s24" in long_list.active_scans


def test_scrolled_away_scans_stay_plotted(long_list):
    long_list.scroll_scans(-100)
    long_list.draw_plot()
    assert [ln.get_label() for ln in long_list.ax.lines] == ["s24: det"]


def test_toggle_scan_after_scrolling(long_list):
    long_list.scroll_scans(-100)
    long_list.on_scan_toggle("s00")
    assert "s00" in long_list.active_scans


@pytest.mark.parametrize(
    "scrolled, expected_last", [(False, "s25"), (True, "s19")], ids=["follow", "kept"]
)
def test_new_scan_follows_unless_scrolled_away(
    many_scans, long_list, scrolled: bool, expected_last: str
):
    if scrolled:
        long_list.scroll_scans(-5)
    many_scans["s25"] = {"det": [1.0]}
    long_list.update_plot()
    assert _shown(long_list)[-1] == expected_last


def test_scrolling_back_to_bottom_resumes_following(many_scans, long_list):
    long_list.scroll_scans(-5)
    long_list.scroll_scans(5)
    many_scans["s25"] = {"det": [1.0]}
    long_list.update_plot()
    assert _shown(long_list)[-1] == "s25"


@pytest.mark.parametrize(
    "rows, header",
    [
        (0, "SCANS  16\u201325/25"),
        (-15, "SCANS  1\u201310/25  \u00b7 +1 selected"),
    ],
)
def test_scan_list_header_shows_position(long_list, rows: int, header: str):
    long_list.scroll_scans(rows)
    assert long_list.ax_scan.get_title(loc="left") == header


def test_short_scan_list_has_plain_header_and_no_scrollbar(window):
    assert window.ax_scan.get_title(loc="left") == "SCANS"
    assert len(window.ax_scan.patches) == 0


def test_long_scan_list_draws_scrollbar(long_list):
    assert len(long_list.ax_scan.patches) == 2


def _mouse(win, name: str, x: float, y: float, **kwargs):
    from matplotlib.backend_bases import MouseEvent

    px, py = win.ax_scan.transAxes.transform((x, y))
    return MouseEvent(name, win.fig.canvas, px, py, **kwargs)


@pytest.mark.parametrize(
    "button, first", [("up", 14), ("down", 15)], ids=["wheel-up", "wheel-down"]
)
def test_mouse_wheel_over_list_scrolls(long_list, button: str, first: int):
    long_list.on_scroll(
        _mouse(
            long_list,
            "scroll_event",
            0.5,
            0.5,
            button=button,
            step=1 if button == "up" else -1,
        )
    )
    assert _shown(long_list)[0] == f"s{first:02d}"


def test_mouse_wheel_elsewhere_does_not_scroll(long_list):
    from matplotlib.backend_bases import MouseEvent

    px, py = long_list.ax.transAxes.transform((0.5, 0.5))
    long_list.on_scroll(
        MouseEvent("scroll_event", long_list.fig.canvas, px, py, button="up", step=1)
    )
    assert _shown(long_list)[0] == "s15"


@pytest.mark.parametrize("y, first", [(0.99, 0), (0.5, 8), (0.01, 15)])
def test_clicking_scroll_track_jumps(long_list, y: float, first: int):
    long_list.on_list_click(_mouse(long_list, "button_press_event", 0.97, y, button=1))
    assert _shown(long_list)[0] == f"s{first:02d}"


def test_clicking_list_labels_does_not_jump(long_list):
    long_list.on_list_click(
        _mouse(long_list, "button_press_event", 0.3, 0.99, button=1)
    )
    assert _shown(long_list)[0] == "s15"


def test_submitting_scan_id_scrolls_it_into_view(long_list):
    long_list.submit_scan("s02")
    assert "s02" in _shown(long_list)


# --- Scrollable channel lists ---------------------------------------------------


@pytest.fixture
def many_channels():
    """One scan with 20 channels: 21 X options, 20 Y channels."""
    return {"s": {f"ch{i:02d}": [1.0, 2.0, 3.0] for i in range(20)}}


@pytest.fixture
def channel_window(many_channels):
    return InteractivePlotWindow(many_channels)


def _labels(win: InteractivePlotWindow, key: str) -> list[str]:
    return [t.get_text() for t in win.widgets[key].labels]


@pytest.mark.parametrize(
    "key, first, last",
    [("radio_x", "Point number", "ch06"), ("check_y", "ch00", "ch07")],
)
def test_channel_lists_show_first_rows(channel_window, key, first, last):
    labels = _labels(channel_window, key)
    assert (len(labels), labels[0], labels[-1]) == (8, first, last)


@pytest.mark.parametrize(
    "name, key, rows, first",
    [
        ("x", "radio_x", 3, "ch02"),
        ("x", "radio_x", 100, "ch12"),
        ("y", "check_y", 2, "ch02"),
        ("y", "check_y", 100, "ch12"),
        ("y", "check_y", -5, "ch00"),
    ],
)
def test_scroll_channel_list_moves_and_clamps(channel_window, name, key, rows, first):
    channel_window.scroll_list(name, rows)
    assert _labels(channel_window, key)[0] == first


@pytest.mark.parametrize(
    "name, header",
    [
        ("x", "X AXIS  1\u20138/21"),
        ("y", "Y CHANNELS  1\u20138/20"),
    ],
)
def test_channel_list_header_shows_position(channel_window, name, header):
    assert channel_window._list_axes()[name].get_title(loc="left") == header


def test_short_channel_lists_not_scrollable(window):
    assert (window.ax_x.get_title(loc="left"), len(window.ax_y.patches)) == (
        "X AXIS",
        0,
    )


@pytest.mark.parametrize("name", ["x", "y"])
def test_long_channel_lists_draw_scrollbar(channel_window, name):
    assert len(channel_window._list_axes()[name].patches) == 2


def test_selected_x_kept_when_scrolled_away(channel_window):
    channel_window.scroll_list("x", 5)
    channel_window.on_x_change("ch10")
    channel_window.scroll_list("x", -100)
    channel_window.draw_plot()
    assert channel_window.ax.get_xlabel() == "ch10"


def test_selected_x_named_in_header_when_scrolled_away(channel_window):
    channel_window.scroll_list("x", 5)
    channel_window.on_x_change("ch10")
    channel_window.scroll_list("x", -100)
    assert channel_window.ax_x.get_title(loc="left").endswith("\u00b7 ch10")


def test_no_x_button_selected_when_selection_scrolled_away(channel_window):
    channel_window.scroll_list("x", 5)
    facecolours = channel_window.widgets["radio_x"]._buttons.get_facecolor()
    assert all(alpha == 0 for *_, alpha in facecolours)


def test_ticked_y_kept_when_scrolled_away(channel_window):
    channel_window.scroll_list("y", 100)
    channel_window.draw_plot()
    assert [ln.get_label() for ln in channel_window.ax.lines] == ["s: ch00"]


def test_hidden_ticked_y_counted_in_header(channel_window):
    channel_window.scroll_list("y", 100)
    assert channel_window.ax_y.get_title(loc="left").endswith("\u00b7 +1 ticked")


def test_tick_y_after_scrolling(channel_window):
    channel_window.scroll_list("y", 100)
    channel_window.on_y_toggle("ch19")
    assert channel_window.active_y_states["ch19"] is True


def test_channel_scroll_position_survives_new_points(many_channels, channel_window):
    channel_window.scroll_list("y", 4)
    for column in many_channels["s"].values():
        column.append(4.0)
    channel_window.update_plot()
    assert _labels(channel_window, "check_y")[0] == "ch04"


@pytest.mark.parametrize("name", ["x", "y", "z"])
def test_2d_lists_scroll(many_channels, name):
    win = InteractivePlotWindow(many_channels)
    win.on_mode_change(PlotMode.GRID_2D)
    win.scroll_list(name, 100)
    assert _labels(win, f"radio_{name}")[-1] == "ch19"


def test_2d_selection_named_in_header_when_scrolled_away(many_channels):
    win = InteractivePlotWindow(many_channels)
    win.on_mode_change(PlotMode.GRID_2D)
    win.scroll_list("z", 100)
    assert win.ax_z.get_title(loc="left").endswith("\u00b7 ch02")


@pytest.mark.parametrize("name", ["x", "y"])
def test_mouse_wheel_scrolls_channel_list(channel_window, name):
    from matplotlib.backend_bases import MouseEvent

    ax = channel_window._list_axes()[name]
    px, py = ax.transAxes.transform((0.5, 0.5))
    channel_window.on_scroll(
        MouseEvent(
            "scroll_event", channel_window.fig.canvas, px, py, button="down", step=-1
        )
    )
    assert channel_window._list_offset(name) == 1


def test_clicking_channel_scroll_track_jumps(channel_window):
    from matplotlib.backend_bases import MouseEvent

    px, py = channel_window.ax_y.transAxes.transform((0.97, 0.01))
    channel_window.on_list_click(
        MouseEvent("button_press_event", channel_window.fig.canvas, px, py, button=1)
    )
    assert _labels(channel_window, "check_y")[-1] == "ch19"
