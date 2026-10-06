from typing import Any

import click


class InteractivePlotWindow:
    def __init__(
        self,
        data_source: dict[str, dict[str, list[Any]]],
        initial_scan_id: Any | None = None,
    ):
        try:
            import matplotlib.pyplot as plt
            from matplotlib.widgets import Button, CheckButtons, RadioButtons, TextBox
        except ImportError:
            click.secho(
                "matplotlib is required for plotting. Install it to use this feature.",
                fg="red",
            )
            raise

        self.plt = plt
        self.CheckButtons = CheckButtons
        self.RadioButtons = RadioButtons
        self.TextBox = TextBox
        self.Button = Button

        self.data_source = data_source
        self.scans = list(self.data_source.keys())
        self.active_scans: set[Any] = set()

        if initial_scan_id in self.scans:
            self.active_scans.add(initial_scan_id)
        elif self.scans:
            self.active_scans.add(self.scans[-1])

        self.active_y_states: dict[str, bool] = {}
        self.last_seen_points: dict[Any, int] = {}

        self.widgets: dict[str, Any] = {}

        self.fig, self.ax = self.plt.subplots(figsize=(10, 6))
        self.plt.subplots_adjust(left=0.08, right=0.72, top=0.95, bottom=0.1)

        self.ax_scan_txt = self.plt.axes((0.76, 0.91, 0.22, 0.04))
        self.ax_scan = self.plt.axes((0.76, 0.62, 0.22, 0.25))
        self.ax_scan_btn = self.plt.axes((0.76, 0.58, 0.22, 0.03))
        self.ax_x = self.plt.axes((0.76, 0.33, 0.22, 0.21))
        self.ax_y = self.plt.axes((0.76, 0.05, 0.22, 0.23))

        # Text box for adding scan
        self.ax_scan_txt.set_title("Add Scan ID", fontsize=10, fontweight="bold")
        self.widgets["text_box"] = self.TextBox(self.ax_scan_txt, "", initial="")
        self.widgets["text_box"].on_submit(self.submit_scan)

        # Unselect scan
        self.widgets["unselect_btn"] = self.Button(self.ax_scan_btn, "Unselect All")
        self.widgets["unselect_btn"].on_clicked(self.unselect_all)

        self.timer = self.fig.canvas.new_timer(interval=1000)
        self.timer.add_callback(self.update_plot)

        self.build_ui()
        self.draw_plot()

        self.fig.canvas.mpl_connect("close_event", self.on_close)

        self.timer.start()
        self.plt.show(block=False)

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

    def build_ui(self) -> None:
        self.ax_scan.cla()
        self.ax_x.cla()
        self.ax_y.cla()

        vis_scans = self.get_visible_scans()
        scan_labels = [str(s) for s in vis_scans]

        self.ax_scan.set_title("Recent / Active Scans", fontsize=10, fontweight="bold")
        self.widgets["scan_check"] = self.CheckButtons(
            self.ax_scan,
            scan_labels,
            actives=[(s in self.active_scans) for s in vis_scans],
        )

        self.ax_x.set_title("X Axis", fontsize=10, fontweight="bold")
        fields = self.get_active_fields()
        x_options = ["Point number"] + fields

        old_x = None
        if "radio_x" in self.widgets:
            old_x = self.widgets["radio_x"].value_selected

        active_x_idx = 0
        if old_x in x_options:
            active_x_idx = x_options.index(old_x)

        self.widgets["radio_x"] = self.RadioButtons(
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

        self.widgets["check_y"] = self.CheckButtons(
            self.ax_y,
            fields,
            actives=[self.active_y_states[f] for f in fields] if fields else [],
        )

        self.widgets["radio_x"].on_clicked(self.on_x_change)
        self.widgets["check_y"].on_clicked(self.on_y_toggle)
        self.widgets["scan_check"].on_clicked(self.on_scan_toggle)

    def on_x_change(self, label: str | None) -> None:
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
        self.fig.canvas.draw_idle()

    def update_plot(self) -> None:
        if not self.plt.fignum_exists(self.fig.number):
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
