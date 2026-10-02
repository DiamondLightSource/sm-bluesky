from unittest.mock import patch

import matplotlib
import matplotlib.pyplot as plt
import pytest

from sm_bluesky.common.clients.interactive_plot import InteractivePlotWindow

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


def test_init(window):
    assert "scan1" in window.active_scans
    assert len(window.scans) == 2
    assert "text_box" in window.widgets
    assert "unselect_btn" in window.widgets
    assert "scan_check" in window.widgets
    assert "radio_x" in window.widgets
    assert "check_y" in window.widgets


def test_get_active_fields(window):
    fields = window.get_active_fields()
    assert "Point number" in fields
    assert "motor1" in fields
    assert "det1" in fields
    assert "motor2" not in fields


def test_get_visible_scans(window):
    large_data = {f"scan{i}": {"Point number": [1]} for i in range(15)}
    win = InteractivePlotWindow(large_data)
    win.active_scans.add("scan1")
    win.active_scans.add("scan10")

    vis = win.get_visible_scans()
    assert len(vis) == 10
    assert "scan1" in vis
    assert "scan10" in vis
    assert "scan14" in vis


def test_unselect_all(window):
    window.unselect_all(None)
    assert len(window.active_scans) == 0


def test_submit_scan_valid(window):
    window.active_scans.clear()
    window.submit_scan("scan2")
    assert "scan2" in window.active_scans


def test_submit_scan_invalid(window):
    window.submit_scan("scan_missing")
    assert "scan_missing" not in window.active_scans


def test_submit_scan_empty_or_error(window):
    initial_scans = set(window.active_scans)
    window.submit_scan("")
    assert window.active_scans == initial_scans

    window.submit_scan("Not found: 123")
    assert window.active_scans == initial_scans


def test_on_x_change(window):
    with patch.object(window, "draw_plot") as mock_draw:
        window.on_x_change("motor1")
        mock_draw.assert_called_once()


def test_on_y_toggle(window):
    window.active_y_states["det1"] = False
    with patch.object(window, "draw_plot") as mock_draw:
        window.on_y_toggle("det1")
        assert window.active_y_states["det1"] is True
        mock_draw.assert_called_once()

    window.on_y_toggle("det1")
    assert window.active_y_states["det1"] is False
    window.on_y_toggle(None)


def test_on_scan_toggle(window):
    window.active_scans.clear()
    window.on_scan_toggle("scan2")
    assert "scan2" in window.active_scans
    window.on_scan_toggle("scan2")
    assert "scan2" not in window.active_scans
    window.on_scan_toggle(None)


def test_update_plot(window):
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


def test_update_plot_closed(window):
    plt.close(window.fig)
    with patch.object(window, "draw_plot") as mock_draw:
        window.update_plot()
        mock_draw.assert_not_called()


def test_on_close(window):
    with patch.object(window.timer, "stop") as mock_timer_stop:
        window.on_close(None)
        mock_timer_stop.assert_called_once()


def test_missing_matplotlib(monkeypatch, sample_data):
    import builtins

    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "matplotlib.pyplot":
            raise ImportError("mock error")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)
    with pytest.raises(ImportError):
        InteractivePlotWindow(sample_data)


def test_draw_with_x_choice(window):
    class MockRadio:
        value_selected = "motor1"

    window.widgets["radio_x"] = MockRadio()
    with patch.object(window.ax, "set_xlabel") as mock_xlabel:
        window.draw_plot()
        mock_xlabel.assert_called_with("motor1")


def test_on_close_exception(window):
    class BadTimer:
        def __init__(self):
            self.stop_called = False

        def stop(self):
            self.stop_called = True
            raise Exception("Mock crash")

        def remove_callback(self, cb):
            pass

    bad_timer = BadTimer()
    window.timer = bad_timer
    window.on_close(None)

    assert bad_timer.stop_called is True


def test_build_ui_explicitly(window):
    window.data_source["scan1"]["brand_new_motor"] = [5, 10]
    assert "brand_new_motor" not in window.active_y_states
    window.build_ui()
    assert "brand_new_motor" in window.active_y_states


def test_draw_plot_explicitly(window):
    window.active_y_states["det1"] = True
    window.active_scans.add("scan1")
    window.draw_plot()
    assert len(window.ax.lines) > 0
