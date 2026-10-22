from collections.abc import Callable
from enum import StrEnum
from typing import Any

import click
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LogNorm
from matplotlib.tri import Triangulation
from matplotlib.widgets import Button, CheckButtons, RadioButtons, TextBox

from sm_bluesky.common.math.rebinning import (
    extract_xyz,
    grid_heatmap,
)


class PlotMode(StrEnum):
    LINE_1D = "1D Line"
    GRID_2D = "2D Grid"
    CONTOUR_2D = "2D Contour"


NO_FIELDS = "(no data)"


class InteractivePlotWindow:
    def __init__(
        self,
        data_source: dict[str, dict[str, list[Any]]],
        initial_scan_id: Any | None = None,
    ):
        self.data_source = data_source
        self.scans = list(self.data_source.keys())
        self.active_scans: set[Any] = set()

        if initial_scan_id in self.scans:
            self.active_scans.add(initial_scan_id)
        elif self.scans:
            self.active_scans.add(self.scans[-1])

        self.active_y_states: dict[str, bool] = {}
        self.last_seen_points: dict[Any, int] = {}

        self.mode: PlotMode = PlotMode.LINE_1D
        self.log_scale: bool = False
        self.x_field: str | None = None
        self.y_field: str | None = None
        self.z_field: str | None = None

        self.widgets: dict[str, Any] = {}

        self.fig, self.ax = plt.subplots(figsize=(10, 6))
        self.fig.subplots_adjust(left=0.08, right=0.72, top=0.95, bottom=0.1)

        self.ax_scan_txt = plt.axes((0.76, 0.920, 0.21, 0.035))
        self.ax_scan = plt.axes((0.76, 0.735, 0.21, 0.145))
        self.ax_scan_btn = plt.axes((0.76, 0.695, 0.21, 0.030))
        self.ax_mode = plt.axes((0.76, 0.575, 0.21, 0.085))
        self.ax_log = plt.axes((0.76, 0.530, 0.21, 0.035))
        self.ax_x = plt.axes((0.76, 0.315, 0.21, 0.175))
        self.ax_y = plt.axes((0.76, 0.070, 0.21, 0.175))
        self.ax_z = plt.axes((0.76, 0.070, 0.21, 0.115))
        self.ax_cbar = plt.axes((0.670, 0.10, 0.020, 0.83))
        self.ax_z.set_visible(False)
        self.ax_cbar.set_visible(False)

        # Text box for adding scan
        self.ax_scan_txt.set_title("Add Scan ID", fontsize=10, fontweight="bold")
        self.widgets["text_box"] = TextBox(self.ax_scan_txt, "", initial="")
        self.widgets["text_box"].on_submit(self.submit_scan)

        # Unselect scan
        self.widgets["unselect_btn"] = Button(self.ax_scan_btn, "Unselect All")
        self.widgets["unselect_btn"].on_clicked(self.unselect_all)

        # Plot mode
        self.ax_mode.set_title("Plot Mode", fontsize=10, fontweight="bold")
        self.widgets["mode_radio"] = RadioButtons(
            self.ax_mode, list(PlotMode), active=0
        )
        self.widgets["mode_radio"].on_clicked(self.on_mode_change)

        self.timer = self.fig.canvas.new_timer(interval=1000)
        self.timer.add_callback(self.update_plot)

        self.build_ui()
        self.draw_plot()

        self.fig.canvas.mpl_connect("close_event", self.on_close)

        self.timer.start()
        plt.show(block=False)

    def on_close(self, event: Any) -> None:
        if hasattr(self, "timer"):
            try:
                self.timer.stop()
                self.timer.remove_callback(self.update_plot)
            except Exception:
                pass

    def submit_scan(self, text: str) -> None:
        if not text or text.startswith("Not found:"):
            return
        s_id = int(text) if text.isdigit() else text
        if s_id in self.data_source:
            self.active_scans.add(s_id)
            self.widgets["text_box"].set_val("")
            self.build_ui()
            self.draw_plot()
        else:
            click.secho(f"Scan '{s_id}' not found.", fg="red")
            self.widgets["text_box"].eventson = False
            self.widgets["text_box"].set_val(f"Not found: {text}")
            self.widgets["text_box"].eventson = True
            self.fig.canvas.draw_idle()

    def unselect_all(self, event: Any) -> None:
        self.active_scans.clear()
        self.build_ui()
        self.draw_plot()

    def get_active_fields(self) -> list[str]:
        fields = set()
        for s_id in self.active_scans:
            fields.update(self.data_source[s_id].keys())
        return sorted(fields)

    def get_visible_scans(self) -> list[Any]:
        max_items = 10
        visible = list(self.active_scans)
        for s in reversed(self.scans):
            if len(visible) >= max_items:
                break
            if s not in visible:
                visible.append(s)
        visible.sort(key=lambda s: self.scans.index(s))
        return visible

    def get_2d_scan(self) -> Any | None:
        if not self.active_scans:
            return None
        n_scans = len(self.scans)
        return max(
            self.active_scans,
            key=lambda s: self.scans.index(s) if s in self.scans else n_scans,
        )

    def get_2d_fields(self) -> list[str]:
        s_id = self.get_2d_scan()
        if s_id is None:
            return []
        return list(self.data_source[s_id].keys())

    def _clear_widgets(self, *names: str) -> None:
        for name in names:
            widget = self.widgets.pop(name, None)
            disconnect = getattr(widget, "disconnect_events", None)
            if disconnect is not None:
                disconnect()

    def _apply_layout(self) -> None:
        self.ax_scan_txt.set_position((0.76, 0.920, 0.21, 0.035))
        self.ax_scan.set_position((0.76, 0.735, 0.21, 0.145))
        self.ax_scan_btn.set_position((0.76, 0.695, 0.21, 0.030))
        self.ax_mode.set_position((0.76, 0.575, 0.21, 0.085))
        self.ax_log.set_position((0.76, 0.530, 0.21, 0.035))

        if self.mode in (PlotMode.GRID_2D, PlotMode.CONTOUR_2D):
            self.ax.set_position((0.09, 0.10, 0.56, 0.83))
            self.ax_cbar.set_position((0.670, 0.10, 0.020, 0.83))
            self.ax_cbar.set_visible(True)
            self.ax_x.set_position((0.76, 0.380, 0.21, 0.115))
            self.ax_y.set_position((0.76, 0.225, 0.21, 0.115))
            self.ax_z.set_position((0.76, 0.070, 0.21, 0.115))
            self.ax_z.set_visible(True)
        else:
            self.ax.set_position((0.09, 0.10, 0.63, 0.83))
            self.ax_cbar.cla()
            self.ax_cbar.set_visible(False)
            self.ax_x.set_position((0.76, 0.315, 0.21, 0.175))
            self.ax_y.set_position((0.76, 0.070, 0.21, 0.175))
            self.ax_z.cla()
            self.ax_z.set_visible(False)

    def build_ui(self) -> None:
        old_x = (
            self.widgets["radio_x"].value_selected
            if "radio_x" in self.widgets
            else self.x_field
        )
        self._clear_widgets(
            "scan_check", "check_log", "radio_x", "check_y", "radio_y", "radio_z"
        )
        self.ax_scan.cla()
        self.ax_log.cla()
        self.ax_x.cla()
        self.ax_y.cla()
        self.ax_z.cla()

        vis_scans = self.get_visible_scans()
        scan_labels = [str(s) for s in vis_scans]

        self.ax_scan.set_title("Recent / Active Scans", fontsize=10, fontweight="bold")
        self.widgets["scan_check"] = CheckButtons(
            self.ax_scan,
            scan_labels,
            actives=[(s in self.active_scans) for s in vis_scans],
        )

        self.widgets["check_log"] = CheckButtons(
            self.ax_log,
            ["Log Scale"],
            actives=[self.log_scale],
        )
        self.widgets["check_log"].on_clicked(self.on_log_toggle)

        self._apply_layout()
        if self.mode in (PlotMode.GRID_2D, PlotMode.CONTOUR_2D):
            self._build_controls_2d()
        else:
            self._build_controls_1d(old_x)

        self.widgets["scan_check"].on_clicked(self.on_scan_toggle)

    def _build_controls_1d(self, old_x: str | None = None) -> None:
        self.ax_x.set_title("X Axis", fontsize=10, fontweight="bold")
        fields = self.get_active_fields()
        x_options = ["Point number"] + fields

        active_x_idx = 0
        if old_x in x_options:
            active_x_idx = x_options.index(old_x)

        self.widgets["radio_x"] = RadioButtons(
            self.ax_x, x_options, active=active_x_idx
        )

        self.ax_y.set_title("Y Channels", fontsize=10, fontweight="bold")
        new_active_y = {}
        for i, f in enumerate(fields):
            if f in self.active_y_states:
                new_active_y[f] = self.active_y_states[f]
            else:
                new_active_y[f] = i == 0 and not any(self.active_y_states.values())
        self.active_y_states.clear()
        self.active_y_states.update(new_active_y)

        self.widgets["check_y"] = CheckButtons(
            self.ax_y,
            fields,
            actives=[self.active_y_states[f] for f in fields] if fields else [],
        )

        self.widgets["radio_x"].on_clicked(self.on_x_change)
        self.widgets["check_y"].on_clicked(self.on_y_toggle)

    def _resolve_2d_fields(self, fields: list[str]) -> None:
        if not fields:
            self.x_field = self.y_field = self.z_field = None
            return

        candidates = [f for f in fields if f != "Point number"] or fields
        defaults = (
            candidates[0],
            candidates[1] if len(candidates) > 1 else candidates[0],
            candidates[2] if len(candidates) > 2 else candidates[-1],
        )
        if self.x_field not in fields:
            self.x_field = defaults[0]
        if self.y_field not in fields:
            self.y_field = defaults[1]
        if self.z_field not in fields:
            self.z_field = defaults[2]

    def _build_controls_2d(self) -> None:

        fields = self.get_2d_fields()
        self._resolve_2d_fields(fields)
        options = fields or [NO_FIELDS]

        def active_idx(selected: str | None) -> int:
            return options.index(selected) if selected in options else 0

        self.ax_x.set_title("X", fontsize=10, fontweight="bold")
        self.ax_y.set_title("Y", fontsize=10, fontweight="bold")
        self.ax_z.set_title("Z", fontsize=10, fontweight="bold")

        self.widgets["radio_x"] = RadioButtons(
            self.ax_x, options, active=active_idx(self.x_field)
        )
        self.widgets["radio_y"] = RadioButtons(
            self.ax_y, options, active=active_idx(self.y_field)
        )
        self.widgets["radio_z"] = RadioButtons(
            self.ax_z, options, active=active_idx(self.z_field)
        )

        self.widgets["radio_x"].on_clicked(self.on_x_change)
        self.widgets["radio_y"].on_clicked(self.on_y_change)
        self.widgets["radio_z"].on_clicked(self.on_z_change)

    def on_mode_change(self, label: str | None) -> None:
        if label is None or label == self.mode:
            return
        try:
            self.mode = PlotMode(label)
        except ValueError:
            return
        self.build_ui()
        self.draw_plot()

    def on_log_toggle(self, label: str | None) -> None:
        if label == "Log Scale":
            self.log_scale = not self.log_scale
            self.draw_plot()

    def on_x_change(self, label: str | None) -> None:
        if self.mode in (PlotMode.GRID_2D, PlotMode.CONTOUR_2D) and label not in (
            None,
            NO_FIELDS,
        ):
            self.x_field = label
        self.draw_plot()

    def on_y_change(self, label: str | None) -> None:
        if label not in (None, NO_FIELDS):
            self.y_field = label
        self.draw_plot()

    def on_z_change(self, label: str | None) -> None:
        if label not in (None, NO_FIELDS):
            self.z_field = label
        self.draw_plot()

    def on_y_toggle(self, label: str | None) -> None:
        if label is not None:
            self.active_y_states[label] = not self.active_y_states.get(label, False)
        self.draw_plot()

    def on_scan_toggle(self, label: str | None) -> None:
        if label is None:
            return

        vis_scans = self.get_visible_scans()
        for s in vis_scans:
            if str(s) == label:
                if s in self.active_scans:
                    self.active_scans.remove(s)
                else:
                    self.active_scans.add(s)
                break
        self.build_ui()
        self.draw_plot()

    def draw_plot(self) -> None:
        if self.mode == PlotMode.GRID_2D:
            self._draw_2d()
        elif self.mode == PlotMode.CONTOUR_2D:
            self._draw_contour()
        else:
            self._draw_1d()

    def _draw_1d(self) -> None:
        self.ax.cla()
        x_widget = self.widgets.get("radio_x")
        x_choice = x_widget.value_selected if x_widget else "Point number"

        if x_choice != "Point number":
            for s_id in self.active_scans:
                if x_choice not in self.data_source[s_id]:
                    x_choice = "Point number"
                    break

        plotted_any = False
        for s_id in self.active_scans:
            s_data = self.data_source[s_id]

            if x_choice == "Point number" or x_choice not in s_data:
                first_key = next(iter(s_data.keys())) if s_data else None
                n_pts = len(s_data[first_key]) if first_key else 0
                x_vals = list(range(1, n_pts + 1))
            else:
                x_vals = s_data[x_choice]

            for y_field, is_active in self.active_y_states.items():
                if is_active and y_field in s_data:
                    y_vals = s_data[y_field]
                    min_len = min(len(x_vals), len(y_vals))
                    self.ax.plot(
                        x_vals[:min_len],
                        y_vals[:min_len],
                        marker="o",
                        label=f"Scan {s_id}: {y_field}",
                    )
                    plotted_any = True

        self.ax.set_xlabel(x_choice)
        self.ax.set_title("Nearly Live Plot")
        self.ax.grid(True)
        if plotted_any:
            self.ax.legend(loc="best")
        if self.log_scale:
            has_pos = any(
                any(v > 0 for v in self.data_source[s_id].get(y_field, []))
                for s_id in self.active_scans
                for y_field, is_active in self.active_y_states.items()
                if is_active
            )
            if has_pos:
                self.ax.set_yscale("log")
            else:
                self.ax.set_yscale("linear")
        else:
            self.ax.set_yscale("linear")
        self.fig.canvas.draw_idle()

    def _get_2d_norm(self, zs: list[float]) -> Any:
        if not self.log_scale:
            return None
        positives = [v for v in zs if v > 0]
        if not positives:
            return None
        vmin = min(positives)
        vmax = max(positives)
        if vmin == vmax:
            vmin = vmin * 0.9
            vmax = vmax * 1.1
        return LogNorm(vmin=vmin, vmax=vmax)

    def _draw_2d_plot(
        self,
        render_fn: Callable[[list[float], list[float], list[float], Any], Any],
    ) -> None:
        self.ax.cla()
        self.ax_cbar.cla()
        self.ax_cbar.set_visible(False)

        s_id = self.get_2d_scan()
        if s_id is None:
            self.ax.set_title(f"{self.mode}: no scan selected")
            self.fig.canvas.draw_idle()
            return

        xs, ys, zs = extract_xyz(
            self.data_source[s_id], self.x_field, self.y_field, self.z_field
        )

        self.ax.set_xlabel(self.x_field or "")
        self.ax.set_ylabel(self.y_field or "")
        if not xs:
            self.ax.set_title(f"Scan {s_id}: waiting for data")
            self.ax.grid(True)
            self.fig.canvas.draw_idle()
            return

        norm = self._get_2d_norm(zs)
        mappable = render_fn(xs, ys, zs, norm)

        self.ax_cbar.set_visible(True)
        colorbar = self.fig.colorbar(mappable, cax=self.ax_cbar)
        colorbar.set_label(self.z_field or "")

        self.ax.set_title(f"Scan {s_id}: {self.z_field}")
        self.ax.grid(True)
        self.fig.canvas.draw_idle()

    def _render_heatmap(
        self, xs: list[float], ys: list[float], zs: list[float], norm: Any = None
    ) -> Any:
        heatmap = grid_heatmap(xs, ys, zs)
        if heatmap is not None:
            x_edges, y_edges, grid = heatmap
            return self.ax.pcolormesh(
                x_edges, y_edges, grid, cmap="viridis", shading="flat", norm=norm
            )
        return self.ax.scatter(xs, ys, c=zs, cmap="viridis", norm=norm)

    def _render_contour(
        self, xs: list[float], ys: list[float], zs: list[float], norm: Any = None
    ) -> Any:
        if norm is not None:
            pos_pts = [(x, y, z) for x, y, z in zip(xs, ys, zs, strict=True) if z > 0]
            if len(pos_pts) >= 3 and len({round(p[2], 6) for p in pos_pts}) > 1:
                cx, cy, cz = zip(*pos_pts, strict=False)
                try:
                    tri = Triangulation(cx, cy)
                    levels = np.geomspace(norm.vmin, norm.vmax, 15)
                    return self.ax.tricontourf(
                        tri, cz, levels=levels, cmap="viridis", norm=norm
                    )
                except Exception:
                    pass
        elif len(xs) >= 3 and len({round(v, 6) for v in zs}) > 1:
            try:
                tri = Triangulation(xs, ys)
                return self.ax.tricontourf(tri, zs, cmap="viridis")
            except Exception:
                pass
        return self.ax.scatter(xs, ys, c=zs, cmap="viridis", norm=norm)

    def _draw_2d(self) -> None:
        self._draw_2d_plot(self._render_heatmap)

    def _draw_contour(self) -> None:
        self._draw_2d_plot(self._render_contour)

    def update_plot(self) -> None:
        if not plt.fignum_exists(self.fig.number):
            return

        new_scans = list(self.data_source.keys())
        added = False

        if len(new_scans) > len(self.scans):
            for s in new_scans[len(self.scans) :]:
                self.scans.append(s)
                self.active_scans.add(s)
            added = True

        current_fields = self.get_active_fields()
        if not hasattr(self, "_last_seen_fields"):
            self._last_seen_fields = []
        fields_changed = current_fields != self._last_seen_fields
        if fields_changed:
            self._last_seen_fields = current_fields

        needs_redraw = added or fields_changed
        for s_id in self.active_scans:
            s_data = self.data_source[s_id]
            first_key = next(iter(s_data.keys())) if s_data else None
            n_pts = len(s_data[first_key]) if first_key else 0
            if self.last_seen_points.get(s_id, 0) != n_pts:
                self.last_seen_points[s_id] = n_pts
                needs_redraw = True

        if added or fields_changed:
            self.build_ui()

        if needs_redraw:
            self.draw_plot()
