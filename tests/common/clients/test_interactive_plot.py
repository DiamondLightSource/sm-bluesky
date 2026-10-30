from unittest.mock import patch

import matplotlib
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

matplotlib.use("Agg")


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
    plt.close("all")
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


def test_get_visible_scans(window: InteractivePlotWindow):
    large_data = {f"scan{i}": {"Point number": [1]} for i in range(15)}
    win = InteractivePlotWindow(large_data)
    win.active_scans.add("scan1")
    win.active_scans.add("scan10")

    vis = win.get_visible_scans()
    assert len(vis) == 10
    assert "scan1" in vis
    assert "scan10" in vis
    assert "scan14" in vis


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


def test_submit_scan_empty_or_error(window: InteractivePlotWindow):
    initial_scans = set(window.active_scans)
    window.submit_scan("")
    assert window.active_scans == initial_scans

    window.submit_scan("Not found: 123")
    assert window.active_scans == initial_scans


def test_on_x_change(window: InteractivePlotWindow):
    with patch.object(window, "draw_plot") as mock_draw:
        window.on_x_change("motor1")
        mock_draw.assert_called_once()


def test_on_y_toggle(window: InteractivePlotWindow):
    window.active_y_states["det1"] = False
    with patch.object(window, "draw_plot") as mock_draw:
        window.on_y_toggle("det1")
        assert window.active_y_states["det1"] is True
        mock_draw.assert_called_once()

    window.on_y_toggle("det1")
    assert window.active_y_states["det1"] is False
    window.on_y_toggle(None)


def test_on_scan_toggle(window: InteractivePlotWindow):
    window.active_scans.clear()
    window.on_scan_toggle("scan2")
    assert "scan2" in window.active_scans
    window.on_scan_toggle("scan2")
    assert "scan2" not in window.active_scans
    window.on_scan_toggle(None)


def test_update_plot(window: InteractivePlotWindow):
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
    class MockRadio:
        value_selected = "motor1"

    window.widgets["radio_x"] = MockRadio()
    with patch.object(window.ax, "set_xlabel") as mock_xlabel:
        window.draw_plot()
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
    class MockRadio:
        value_selected = "motor1"

    window.widgets["radio_x"] = MockRadio()
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
    plt.close("all")
    win = InteractivePlotWindow(grid_data, initial_scan_id="grid")
    win.on_mode_change(PlotMode.GRID_2D)
    return win


def test_mode_defaults_to_1d(window: InteractivePlotWindow):
    assert window.mode == PlotMode.LINE_1D
    assert "mode_radio" in window.widgets
    assert not window.ax_cbar.get_visible()
    assert not window.ax_z.get_visible()


def test_switch_to_2d_builds_2d_controls(grid_window: InteractivePlotWindow):
    win = grid_window
    assert win.mode == PlotMode.GRID_2D
    assert "radio_x" in win.widgets
    assert "radio_y" in win.widgets
    assert "radio_z" in win.widgets
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
    assert len(win.ax.lines) == 0
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
    assert "Scan other" in win.ax.get_title()


def test_2d_no_scan_selected(grid_window: InteractivePlotWindow):
    win = grid_window
    win.unselect_all(None)
    assert win.get_2d_scan() is None
    assert win.get_2d_fields() == []
    assert len(win.ax.collections) == 0
    assert "no scan selected" in win.ax.get_title()
    assert (win.x_field, win.y_field, win.z_field) == (None, None, None)


def test_2d_waiting_for_data(grid_data):
    plt.close("all")
    grid_data["grid"] = {"x_motor": [], "y_motor": [], "det": []}
    win = InteractivePlotWindow(grid_data, initial_scan_id="grid")
    win.on_mode_change(PlotMode.GRID_2D)
    assert len(win.ax.collections) == 0
    assert "waiting for data" in win.ax.get_title()
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
    plt.close("all")
    grid_data["grid"] = {"only": [1.0, 2.0]}
    win = InteractivePlotWindow(grid_data, initial_scan_id="grid")
    win.on_mode_change(PlotMode.GRID_2D)
    assert (win.x_field, win.y_field, win.z_field) == ("only", "only", "only")


def test_switch_to_contour_builds_2d_controls(grid_data):
    plt.close("all")
    win = InteractivePlotWindow(grid_data, initial_scan_id="grid")
    win.on_mode_change(PlotMode.CONTOUR_2D)
    assert win.mode == PlotMode.CONTOUR_2D
    assert "radio_x" in win.widgets
    assert "radio_y" in win.widgets
    assert "radio_z" in win.widgets
    assert "check_y" not in win.widgets
    assert win.ax_z.get_visible()
    assert win.ax_cbar.get_visible()


def test_contour_draw_with_colorbar(grid_data):
    plt.close("all")
    win = InteractivePlotWindow(grid_data, initial_scan_id="grid")
    win.on_mode_change(PlotMode.CONTOUR_2D)
    assert win.ax_cbar.get_visible()
    assert win.ax.get_xlabel() == "x_motor"
    assert win.ax.get_ylabel() == "y_motor"
    assert win.ax_cbar.get_ylabel() == "det"
    assert isinstance(win.ax.collections[0], TriContourSet)


def test_contour_draw_fallback_collinear(grid_data):
    plt.close("all")
    grid_data["grid"] = {
        "x_motor": [0.0, 1.0, 2.0],
        "y_motor": [0.0, 0.0, 0.0],
        "det": [1.0, 2.0, 3.0],
    }
    win = InteractivePlotWindow(grid_data, initial_scan_id="grid")
    win.on_mode_change(PlotMode.CONTOUR_2D)
    assert win.ax_cbar.get_visible()
    assert isinstance(win.ax.collections[0], PathCollection)

    win.on_log_toggle("Log Scale")
    assert isinstance(win.ax.collections[0], PathCollection)
    assert isinstance(win.ax.collections[0].norm, LogNorm)


def test_contour_no_scan_selected(grid_data):
    plt.close("all")
    win = InteractivePlotWindow(grid_data, initial_scan_id="grid")
    win.on_mode_change(PlotMode.CONTOUR_2D)
    win.unselect_all(None)
    assert "no scan selected" in win.ax.get_title()
    assert len(win.ax.collections) == 0


def test_contour_waiting_for_data(grid_data):
    plt.close("all")
    grid_data["grid"] = {"x_motor": [], "y_motor": [], "det": []}
    win = InteractivePlotWindow(grid_data, initial_scan_id="grid")
    win.on_mode_change(PlotMode.CONTOUR_2D)
    assert "waiting for data" in win.ax.get_title()
    assert not win.ax_cbar.get_visible()


def test_log_scale_default_false(window: InteractivePlotWindow):
    assert window.log_scale is False
    assert "check_log" in window.widgets


def test_on_log_toggle(window: InteractivePlotWindow):
    with patch.object(window, "draw_plot") as mock_draw:
        window.on_log_toggle("Log Scale")
        assert window.log_scale is True
        mock_draw.assert_called_once()

        window.on_log_toggle("Log Scale")
        assert window.log_scale is False
        assert mock_draw.call_count == 2

    window.on_log_toggle("Other")
    assert window.log_scale is False


def test_1d_log_scale(window: InteractivePlotWindow):
    assert window.ax.get_yscale() == "linear"
    window.on_log_toggle("Log Scale")
    assert window.ax.get_yscale() == "log"
    window.on_log_toggle("Log Scale")
    assert window.ax.get_yscale() == "linear"


def test_1d_log_scale_non_positive():
    plt.close("all")
    data = {"1": {"y1": [-5, 0], "y2": [-1, -2]}}
    win = InteractivePlotWindow(data, initial_scan_id="1")
    win.on_log_toggle("Log Scale")
    assert win.ax.get_yscale() == "linear"


def test_2d_log_scale_heatmap(grid_data):
    plt.close("all")
    win = InteractivePlotWindow(grid_data, initial_scan_id="grid")
    win.on_mode_change(PlotMode.GRID_2D)
    win.on_log_toggle("Log Scale")
    assert isinstance(win.ax.collections[0], QuadMesh)
    mappable = win.ax.collections[0]
    assert isinstance(mappable.norm, LogNorm)
    assert win.ax_cbar.get_visible()


def test_2d_log_scale_contour(grid_data):
    plt.close("all")
    win = InteractivePlotWindow(grid_data, initial_scan_id="grid")
    win.on_mode_change(PlotMode.CONTOUR_2D)
    win.on_log_toggle("Log Scale")
    assert isinstance(win.ax.collections[0], TriContourSet)
    mappable = win.ax.collections[0]
    assert isinstance(mappable.norm, LogNorm)
    assert win.ax_cbar.get_visible()


def test_2d_log_scale_non_positive():
    plt.close("all")
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
    plt.close("all")
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
    plt.close("all")
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
    plt.close("all")
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


def test_2d_contour_large_z_overflow():
    """Ensure z values exceeding 32 bit do not trigger OverflowError
    and default to scatter"""
    plt.close("all")
    data = {
        "scan": {
            "x": [0, 1, 2, 0, 1, 2, 0, 1, 2],
            "y": [0, 0, 0, 1, 1, 1, 2, 2, 2],
            "det": [1e8, 5e8, 4.5e9, 2e8, 3e9, 1e9, 4e8, 2.5e9, 3.5e19],
        }
    }
    win = InteractivePlotWindow(data, initial_scan_id="scan")
    win.on_mode_change(PlotMode.CONTOUR_2D)
    assert isinstance(win.ax.collections[0], TriContourSet)

    win.on_log_toggle("Log Scale")
    assert isinstance(win.ax.collections[0], TriContourSet)


def test_custom_cmap(grid_data):
    plt.close("all")
    win = InteractivePlotWindow(grid_data, initial_scan_id="grid", cmap="plasma")
    win.on_mode_change(PlotMode.GRID_2D)
    assert win.cmap == "plasma"
    assert win.ax.collections[0].get_cmap().name == "plasma"


def test_invalid_cmap_fallback(grid_data):
    plt.close("all")
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
    plt.close("all")
    data = {
        "scan1": {
            "pgm-energy": [1.0, 2.0, 3.0, 4.0],
            "det1": [10.0, 50.0, 20.0, 5.0],
            "fit": [11.0, 48.0, 21.0, 6.0],
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
    assert active_fields == ["det1", "pgm-energy", "fit", "d1", "d2"]
    assert win.active_y_states["det1"] is True
    assert win.active_y_states["fit"] is False

    x_labels = [t.get_text() for t in win.widgets["radio_x"].labels]
    assert x_labels == ["Point number", "det1", "pgm-energy"]
    assert win.get_2d_fields() == ["pgm-energy", "det1"]
