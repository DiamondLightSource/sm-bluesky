from datetime import datetime
from pathlib import Path
from typing import Any

import click
from blueapi.client import BlueapiClient
from blueapi.client.event_bus import AnyEvent
from blueapi.config import (
    ApplicationConfig,
    ConfigLoader,
    HttpUrl,
    RestConfig,
    StompConfig,
    TcpUrl,
)
from blueapi.core import DataEvent

_ACTIVE_WIDGETS: dict[Any, dict[str, Any]] = {}


class BlueAPISession:
    def __init__(
        self, config: ApplicationConfig, instrument_session: str | None = None
    ):
        self._bc: BlueapiClient | None = None
        self.config: ApplicationConfig = config
        self.data: dict[str, dict[str, list[Any]]] = {}
        self.current_scan_id: Any | None = None
        click.echo("Connecting to BlueAPI service...")
        self.bc = BlueapiClient.from_config(self.config)
        self.bc.login()

        self._install_callbacks()
        self.print_inventory()

        if instrument_session:
            self.bc.instrument_session = instrument_session
            click.echo(f"Active instrument session: {instrument_session}")
        else:
            click.secho(
                "\n[Notice] No instrument session set. Set `bc.instrument_session ="
                " '<session_id>'` before dispatching plans.",
                fg="red",
            )

    @property
    def bc(self) -> BlueapiClient:
        if self._bc is None:
            raise RuntimeError("BlueAPI client is not initialized.")
        return self._bc

    @bc.setter
    def bc(self, value: BlueapiClient) -> None:
        self._bc = value

    def start_shell(self) -> None:
        """Start an interactive IPython shell with the BlueAPI client available."""
        from IPython import start_ipython
        from traitlets.config import Config

        c = Config()
        c.InteractiveShellApp.exec_lines = [
            "try:\n    get_ipython().run_line_magic('matplotlib', 'auto')\n    plot_interactive()\nexcept Exception as e:\n    print(f'Failed to start interactive plot: {e}')"
        ]

        c.TerminalInteractiveShell.banner1 = (
            "\nBlueAPI client ready.\n"
            'The client is available as "bc".\n'
            "Use exit() or Ctrl-D to leave.\n"
        )

        start_ipython(
            argv=[],
            config=c,
            user_ns={
                "bc": self.bc,
                "pl": self.bc.plans,
                "dev": self.bc.devices,
                "scan_data": self.data,
                "plot": self.plot,
                "plot_interactive": self.plot_interactive,
            },
        )

    def plot(
        self, x: str | None = None, y: str | None = None, scan_id: Any | None = None
    ) -> None:
        """Plot x vs y from the scan data."""
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            click.secho(
                "matplotlib is required for plotting. Install it to use this feature.",
                fg="red",
            )
            return

        target_scan_id = scan_id or self.current_scan_id
        if target_scan_id is None and self.data:
            target_scan_id = list(self.data.keys())[-1]

        if target_scan_id is None:
            click.secho("No scan data available to plot.", fg="red")
            return

        if target_scan_id not in self.data:
            click.secho(f"Scan ID {target_scan_id} not found in data.", fg="red")
            return

        scan_data = self.data[target_scan_id]
        available_fields = list(scan_data.keys())

        if not available_fields:
            click.secho(f"No fields available in scan {target_scan_id}.", fg="red")
            return

        if x is None and y is None:
            if len(available_fields) >= 2:
                x_key = available_fields[0]
                y_key = available_fields[1]
            else:
                x_key = None
                y_key = available_fields[0]
        elif y is None:
            y_key = x
            x_key = None
        else:
            x_key = x
            y_key = y

        if y_key not in scan_data:
            click.secho(
                f"Data for '{y_key}' not found in scan {target_scan_id}.", fg="red"
            )
            click.echo(f"Available fields: {available_fields}")
            return

        if x_key is not None and x_key not in scan_data:
            click.secho(
                f"Data for '{x_key}' not found in scan {target_scan_id}.", fg="red"
            )
            click.echo(f"Available fields: {available_fields}")
            return

        y_data = scan_data[y_key]

        if x_key is not None:
            x_data = scan_data[x_key]
            min_len = min(len(x_data), len(y_data))
            x_plot = x_data[:min_len]
            y_plot = y_data[:min_len]
            xlabel = x_key
        else:
            x_plot = list(range(1, len(y_data) + 1))
            y_plot = y_data
            xlabel = "Point number"

        plt.figure()
        plt.plot(x_plot, y_plot, marker="o")
        plt.xlabel(xlabel)
        plt.ylabel(y_key)
        title_x = xlabel if x_key is not None else "point number"
        plt.title(f"Scan {target_scan_id}: {title_x} vs {y_key}")
        plt.grid(True)
        plt.show(block=False)

    def plot_interactive(self, scan_id: Any | None = None) -> None:
        """Open an interactive plot window with clickable controls for multiple scans and axes."""
        try:
            import matplotlib.pyplot as plt
            from matplotlib.widgets import Button, CheckButtons, RadioButtons, TextBox
        except ImportError:
            click.secho(
                "matplotlib is required for plotting. Install it to use this feature.",
                fg="red",
            )
            return

        scans = list(self.data.keys())
        active_scans = dict.fromkeys(scans, False)
        if scan_id in active_scans:
            active_scans[scan_id] = True
        elif scans:
            active_scans[scans[-1]] = True

        # Create figure with margin on the right for control panels
        fig, ax = plt.subplots(figsize=(10, 6))
        plt.subplots_adjust(left=0.08, right=0.72, top=0.95, bottom=0.1)

        # Container to hold widgets so Python doesn't garbage collect them
        _ACTIVE_WIDGETS[fig] = {}

        def get_active_fields() -> list[str]:
            fields = set()
            for s_id, is_active in active_scans.items():
                if is_active:
                    fields.update(self.data[s_id].keys())
            return sorted(list(fields))

        def get_visible_scans() -> list[Any]:
            # Always show active scans, fill the rest with most recent up to 10
            max_items = 10
            visible = [s for s in scans if active_scans.get(s, False)]
            for s in reversed(scans):
                if len(visible) >= max_items:
                    break
                if s not in visible:
                    visible.append(s)
            visible.sort(key=lambda s: scans.index(s))
            return visible

        # Widget Axes areas [left, bottom, width, height]
        ax_scan_txt = plt.axes((0.76, 0.91, 0.22, 0.04))
        ax_scan = plt.axes((0.76, 0.62, 0.22, 0.25))
        ax_scan_btn = plt.axes((0.76, 0.58, 0.22, 0.03))
        ax_x = plt.axes((0.76, 0.33, 0.22, 0.21))
        ax_y = plt.axes((0.76, 0.05, 0.22, 0.23))

        # Text Box for explicitly adding a scan
        ax_scan_txt.set_title("Search / Add Scan ID", fontsize=10, fontweight="bold")
        text_box = TextBox(ax_scan_txt, "", initial="")

        def submit_scan(text: str) -> None:
            if not text:
                return
            s_id = int(text) if text.isdigit() else text
            if s_id in self.data:
                active_scans[s_id] = True
                text_box.set_val("")
                build_ui()
                draw_plot()
            else:
                click.secho(f"Scan '{s_id}' not found.", fg="red")

        text_box.on_submit(submit_scan)
        _ACTIVE_WIDGETS[fig]["text_box"] = text_box

        # Unselect All Button
        unselect_btn = Button(ax_scan_btn, "Unselect All")

        def unselect_all(event: Any) -> None:
            for s in active_scans:
                active_scans[s] = False
            build_ui()
            draw_plot()

        unselect_btn.on_clicked(unselect_all)
        _ACTIVE_WIDGETS[fig]["unselect_btn"] = unselect_btn

        active_y_states: dict[str, bool] = {}

        def draw_plot() -> None:
            ax.cla()
            x_widget = _ACTIVE_WIDGETS[fig].get("radio_x")
            x_choice = x_widget.value_selected if x_widget else "Point number"

            plotted_any = False
            for s_id, is_scan_active in active_scans.items():
                if not is_scan_active:
                    continue

                s_data = self.data[s_id]

                # Determine X values
                if x_choice == "Point number" or x_choice not in s_data:
                    first_key = next(iter(s_data.keys())) if s_data else None
                    n_pts = len(s_data[first_key]) if first_key else 0
                    x_vals = list(range(1, n_pts + 1))
                    x_label = "Point number"
                else:
                    x_vals = s_data[x_choice]
                    x_label = x_choice

                # Plot each checked Y channel
                for y_field, is_active in active_y_states.items():
                    if is_active and y_field in s_data:
                        y_vals = s_data[y_field]
                        min_len = min(len(x_vals), len(y_vals))
                        ax.plot(
                            x_vals[:min_len],
                            y_vals[:min_len],
                            marker="o",
                            label=f"Scan {s_id}: {y_field}",
                        )
                        plotted_any = True

            ax.set_xlabel(x_choice if x_widget else "Point number")
            ax.set_title("Live Multi-Scan Plot")
            ax.grid(True)
            if plotted_any:
                ax.legend(loc="best")
            fig.canvas.draw_idle()

        def build_ui() -> None:
            ax_scan.cla()
            ax_x.cla()
            ax_y.cla()

            # 1. Scans (Limit to 10)
            vis_scans = get_visible_scans()
            scan_labels = [str(s) for s in vis_scans]
            scan_check = CheckButtons(
                ax_scan,
                scan_labels,
                actives=[active_scans[s] for s in vis_scans],
            )
            ax_scan.set_title("Recent / Active Scans", fontsize=10, fontweight="bold")

            # 2. X and Y Controls
            fields = get_active_fields()
            x_options = ["Point number"] + fields

            old_x = None
            if "radio_x" in _ACTIVE_WIDGETS[fig]:
                old_x = _ACTIVE_WIDGETS[fig]["radio_x"].value_selected

            active_x_idx = 0
            if old_x in x_options:
                active_x_idx = x_options.index(old_x)

            radio_x = RadioButtons(ax_x, x_options, active=active_x_idx)
            ax_x.set_title("X Axis", fontsize=10, fontweight="bold")

            new_active_y = {}
            for i, f in enumerate(fields):
                if f in active_y_states:
                    new_active_y[f] = active_y_states[f]
                else:
                    new_active_y[f] = i == 0 and not any(active_y_states.values())
            active_y_states.clear()
            active_y_states.update(new_active_y)

            check_y = CheckButtons(
                ax_y,
                fields,
                actives=[active_y_states[f] for f in fields] if fields else [],
            )
            ax_y.set_title("Y Channels", fontsize=10, fontweight="bold")

            def on_x_change(label: str | None) -> None:
                draw_plot()

            def on_y_toggle(label: str | None) -> None:
                if label is not None:
                    active_y_states[label] = not active_y_states.get(label, False)
                draw_plot()

            def on_scan_toggle(label: str | None) -> None:
                if label is None:
                    return
                for s in vis_scans:
                    if str(s) == label:
                        active_scans[s] = not active_scans.get(s, False)
                        break
                build_ui()
                draw_plot()

            radio_x.on_clicked(on_x_change)
            check_y.on_clicked(on_y_toggle)
            scan_check.on_clicked(on_scan_toggle)

            _ACTIVE_WIDGETS[fig]["radio_x"] = radio_x
            _ACTIVE_WIDGETS[fig]["check_y"] = check_y
            _ACTIVE_WIDGETS[fig]["scan_check"] = scan_check

        last_seen_points: dict[Any, int] = {}

        def update_interactive() -> None:
            if not plt.fignum_exists(fig.number):
                timer.stop()
                return

            new_scans = list(self.data.keys())
            added = False
            for s in new_scans:
                if s not in scans:
                    scans.append(s)
                    active_scans[s] = True
                    added = True

            needs_redraw = added
            for s_id, is_active in active_scans.items():
                if is_active and s_id in self.data:
                    s_data = self.data[s_id]
                    first_key = next(iter(s_data.keys())) if s_data else None
                    n_pts = len(s_data[first_key]) if first_key else 0
                    if last_seen_points.get(s_id, 0) != n_pts:
                        last_seen_points[s_id] = n_pts
                        needs_redraw = True

            if added:
                build_ui()

            if needs_redraw:
                draw_plot()

        timer = fig.canvas.new_timer(interval=1000)
        timer.add_callback(update_interactive)
        timer.start()
        _ACTIVE_WIDGETS[fig]["timer"] = timer

        # Initialize and show
        build_ui()
        draw_plot()
        plt.show(block=False)

    def print_inventory(self) -> BlueapiClient:
        """Print available plans and devices."""
        click.echo("\nPlans available:")
        for plan in self.bc.plans:
            click.echo(f"  {plan.name}")

        click.echo("\nDevices available:")
        for device in self.bc.devices:
            click.echo(f"  {device.name}")
        return self.bc

    def _install_callbacks(self) -> None:
        """Install a callback which displays run progress."""

        def feedback(event: AnyEvent) -> None:

            match event:
                case DataEvent(
                    name="start", doc={"scan_id": scan_id, "uid": uid, "time": time}
                ):
                    self.current_scan_id = scan_id
                    self.data[scan_id] = {}

                    click.echo(
                        f"{self._format_time(time)} -"
                        f" Run started (scan_id={scan_id}, uid={uid})"
                    )

                case DataEvent(
                    name="stop",
                    doc={
                        "exit_status": status,
                        "time": time,
                        "uid": uid,
                    },
                ):
                    click.echo(
                        f"{self._format_time(time)} -"
                        f" Run complete (scan_id={self.current_scan_id}, "
                        f"uid: {uid}): {status}"
                    )
                    self.current_scan_id = None

                case DataEvent(
                    name="event",
                    doc={"seq_num": point, "data": event_data, "time": time},
                ):
                    if self.current_scan_id is None:
                        return

                    scan_data = self.data[self.current_scan_id]

                    for device, value in event_data.items():
                        scan_data.setdefault(device, []).append(value)

                    values = ", ".join(
                        f"{name}={value}" for name, value in event_data.items()
                    )
                    click.echo(f"{self._format_time(time)} - Point {point}: {values}")

        callback_id = self.bc.add_callback(feedback)
        click.echo(f"Installed data event callback (id={callback_id}).")

    @staticmethod
    def _format_time(timestamp: int) -> str:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def load_config(
    config_path: Path | None = None,
    beamline: str | None = None,
) -> ApplicationConfig:
    """Load configuration from file orCLI beamline flag"""

    if config_path is not None:
        print(f"Loading configuration from file: {config_path}")
        loader = ConfigLoader(ApplicationConfig)
        loader.use_values_from_yaml(config_path)
        return loader.load()

    target_beamline = beamline

    if not target_beamline:
        raise ValueError(
            "No beamline specified. Please provide either:\n"
            "  --beamline / -b <beamline_name>\n"
            "  --config / -c <path_to_yaml>\n"
        )

    print(f"Connecting using default config for beamline: {target_beamline}")

    return ApplicationConfig(
        api=RestConfig(url=HttpUrl(f"https://{target_beamline}-blueapi.diamond.ac.uk")),
        stomp=StompConfig(
            enabled=True,
            url=TcpUrl(f"tcp://{target_beamline}-rabbitmq-daq.diamond.ac.uk:61613"),
        ),
    )
