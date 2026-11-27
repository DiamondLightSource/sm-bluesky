import time
from collections.abc import Callable, Sequence
from enum import StrEnum
from typing import Any

import click
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import colormaps
from matplotlib.backend_bases import KeyEvent, key_press_handler
from matplotlib.colors import LogNorm
from matplotlib.patches import Rectangle
from matplotlib.ticker import LogFormatterSciNotation, LogLocator
from matplotlib.tri import Triangulation
from matplotlib.widgets import Button, CheckButtons, RadioButtons, TextBox

from sm_bluesky.common.math.conversion import to_float
from sm_bluesky.common.math.rebinning import (
    extract_xyz,
    grid_heatmap,
)


class PlotMode(StrEnum):
    """Supported plotting modes for the interactive plot window."""

    LINE_1D = "1D Line"
    GRID_2D = "2D Grid"
    CONTOUR_2D = "2D Contour"


DEFAULT_CMAP = "viridis"
NO_FIELDS = "(no data)"
POINT_NUMBER = "Point number"
LOG_SCALE = "Log Scale"
FOLLOW_LATEST = "Follow Latest"
# Field names the client's auto-analysis stores alongside the scan data.
FIT_PREFIX = ""
FIT_GAUSSIAN = f"{FIT_PREFIX}gaussian"
FIT_D1 = f"{FIT_PREFIX}d1"
FIT_D2 = f"{FIT_PREFIX}d2"
FIT_CENTRE = f"{FIT_PREFIX}centre"
FIT_COM = f"{FIT_PREFIX}com"
FIT_ZERO_CROSSING = f"{FIT_PREFIX}zero_crossing"
FIT_MAX_SLOPE_X = f"{FIT_PREFIX}max_slope_x"
FIT_MIN_SLOPE_X = f"{FIT_PREFIX}min_slope_x"
DERIVED_Y_FIELDS = (FIT_GAUSSIAN, FIT_D1, FIT_D2)
DERIVATIVE_FIELDS = (FIT_D1, FIT_D2)
SCALAR_META_FIELDS = {
    FIT_CENTRE,
    FIT_COM,
    FIT_ZERO_CROSSING,
    FIT_MAX_SLOPE_X,
    FIT_MIN_SLOPE_X,
}
FIT_FIELDS = frozenset(DERIVED_Y_FIELDS) | SCALAR_META_FIELDS

# --- Look and feel ---------------------------------------------------------
PANEL_COLOUR = "#f3f4f6"
PANEL_EDGE = "#d0d4da"
TEXT_COLOUR = "#1f2328"
MUTED_COLOUR = "#57606a"
ACCENT_COLOUR = "#1f6feb"
GRID_COLOUR = "#d8dce1"
LIVE_COLOUR = "#e5534b"
SCAN_COLOURS = tuple(colormaps["tab10"].colors)  # type: ignore[attr-defined]
CHANNEL_LINESTYLES = ("-", "--", "-.", ":")
# Rows shown in the scan list; older scans are reached by scrolling.
MAX_VISIBLE_SCANS = 10
# Rows shown in the X / Y / Z channel lists before they scroll.
MAX_VISIBLE_CHANNELS = 8
# Longest field name shown in a list header for an off-screen selection.
HEADER_NAME_CHARS = 12
SCROLLBAR_X = 0.955
SCROLLBAR_W = 0.035
SCROLL_TRACK_COLOUR = "#e1e4e8"
SCROLL_THUMB_COLOUR = "#8c959f"
# Draw point markers only while a line has few enough points to read them.
MARKER_POINT_LIMIT = 60
KEY_HELP = "Keys: l log · m mode · n newest · u clear"

# Control column geometry, in figure fractions.
PANEL_LEFT = 0.745
PANEL_X = 0.760
PANEL_W = 0.225
PANEL_TOP = 0.968
PANEL_BOTTOM = 0.055
HEADER_H = 0.028
SECTION_GAP = 0.010
MAX_ROW_H = 0.030
TEXTBOX_H = 0.036
BUTTON_H = 0.034


def _as_floats(values: Sequence[Any]) -> np.ndarray:
    """Convert readings to floats, with NaN for anything non-numeric."""
    return np.array(
        [number if (number := to_float(v)) is not None else np.nan for v in values],
        dtype=float,
    )


def _styled(widget_cls: type, ax: Any, *args: Any, **style: Any) -> Any:
    """Create a widget with styling, falling back for older matplotlib.

    Per-label style lists cannot be empty, so an empty widget is unstyled.
    """
    labels = args[0] if args else None
    if labels is not None and len(labels) == 0:
        plain = {k: v for k, v in style.items() if not k.endswith("_props")}
        return widget_cls(ax, *args, **plain)
    try:
        return widget_cls(ax, *args, **style)
    except TypeError:
        return widget_cls(ax, *args)


class InteractivePlotWindow:
    """Interactive Matplotlib window for live plotting of 1D and 2D scan data.

    Provides UI controls to select active scans, switch between 1D line,
    2D grid heatmap, and 2D contour plot modes, toggle logarithmic scaling,
    and choose X/Y/Z data channels.

    Each scan keeps the same colour while the window is open, and fit results
    are overlaid in that colour (Gaussian dashed, derivatives on a right-hand
    axis). Keyboard shortcuts: ``l`` log scale, ``m`` next plot mode, ``n``
    show only the newest scan, ``u`` clear the selection.

    Parameters
    ----------
    data_source : dict[str, dict[str, list[Any]]]
        Mapping of scan IDs to dictionaries of field names and their data lists.
    initial_scan_id : Any | None, optional
        Scan ID to select initially. If not found or None, defaults to the most
        recent scan in ``data_source``.
    cmap : str, optional
        Matplotlib colormap name used for 2D plots. Defaults to ``"viridis"``.
    """

    def __init__(
        self,
        data_source: dict[str, dict[str, list[Any]]],
        initial_scan_id: Any | None = None,
        cmap: str = DEFAULT_CMAP,
    ):
        self.data_source = data_source
        self.scans = list(self.data_source.keys())
        self.active_scans: set[Any] = set()
        # The dict object behind each scan id, so a scan replaced under the
        # same id (e.g. after an instrument-session change) is detected.
        self._scan_refs: dict[Any, Any] = {s: data_source[s] for s in self.scans}
        self._last_seen_fields: list[str] = []
        self._last_seen_2d_fields: list[str] = []

        if initial_scan_id in self.scans:
            self.active_scans.add(initial_scan_id)
        elif self.scans:
            self.active_scans.add(self.scans[-1])

        if cmap not in colormaps:
            click.secho(
                f"Unknown colormap '{cmap}', falling back to '{DEFAULT_CMAP}'.",
                fg="yellow",
            )
            cmap = DEFAULT_CMAP
        self.cmap: str = cmap

        self.active_y_states: dict[str, bool] = {}
        self.last_seen_points: dict[Any, int] = {}

        self.mode: PlotMode = PlotMode.LINE_1D
        self.log_scale: bool = False
        # When on, a newly started scan replaces the selection instead of
        # being added to it.
        self.follow_latest: bool = False
        # First row shown in the scan list; None keeps the newest scans in view.
        self.scan_offset: int | None = None
        # First row shown in each channel list (they start at the top).
        self.list_offsets: dict[str, int] = {"x": 0, "y": 0, "z": 0}
        # Selected 1D x axis; kept here because it may be scrolled out of view.
        self.line_x: str = POINT_NUMBER
        self.x_field: str | None = None
        self.y_field: str | None = None
        self.z_field: str | None = None

        self.widgets: dict[str, Any] = {}

        self.fig = plt.figure(figsize=(11, 6.5), facecolor="white")
        manager = self.fig.canvas.manager
        if manager is not None:
            manager.set_window_title("sm-bluesky live plot")
        self.fig.patches.append(
            Rectangle(
                (PANEL_LEFT, 0.0),
                1.0 - PANEL_LEFT,
                1.0,
                transform=self.fig.transFigure,
                facecolor=PANEL_COLOUR,
                edgecolor=PANEL_EDGE,
                linewidth=0.8,
                zorder=-10,
            )
        )

        self.ax = self.fig.add_axes((0.07, 0.11, 0.63, 0.82))
        # Right-hand axis for derivatives, whose scale differs from the data.
        self.ax_d = self.ax.twinx()
        self.ax_d.set_visible(False)

        self.ax_scan_txt = self._panel_axes()
        self.ax_scan = self._panel_axes()
        self.ax_scan_btn = self._panel_axes()
        self.ax_latest_btn = self._panel_axes()
        self.ax_mode = self._panel_axes()
        self.ax_log = self._panel_axes()
        self.ax_x = self._panel_axes()
        self.ax_y = self._panel_axes()
        self.ax_z = self._panel_axes()
        self.ax_cbar = self.fig.add_axes((0.672, 0.11, 0.018, 0.82))
        self.ax_z.set_visible(False)
        self.ax_cbar.set_visible(False)

        self._status_text = self.fig.text(
            0.07, 0.022, "", fontsize=8.5, color=MUTED_COLOUR, ha="left"
        )
        self.fig.text(
            PANEL_X, 0.020, KEY_HELP, fontsize=7.5, color=MUTED_COLOUR, ha="left"
        )

        # Text box for adding scan
        self.widgets["text_box"] = TextBox(
            self.ax_scan_txt, "", initial="", color="white", hovercolor="#fafbfc"
        )
        self.widgets["text_box"].on_submit(self.submit_scan)

        # Selection shortcuts
        self.widgets["unselect_btn"] = Button(
            self.ax_scan_btn, "Clear", color="white", hovercolor="#e8eaed"
        )
        self.widgets["unselect_btn"].on_clicked(self.unselect_all)
        self.widgets["latest_btn"] = Button(
            self.ax_latest_btn, "Newest only", color="white", hovercolor="#e8eaed"
        )
        self.widgets["latest_btn"].on_clicked(self.select_latest)
        for button in (self.widgets["unselect_btn"], self.widgets["latest_btn"]):
            button.label.set_fontsize(8.5)
            button.label.set_color(TEXT_COLOUR)

        # Plot mode
        self.widgets["mode_radio"] = _styled(
            RadioButtons,
            self.ax_mode,
            list(PlotMode),
            active=0,
            activecolor=ACCENT_COLOUR,
            label_props={"fontsize": [9] * len(PlotMode)},
        )
        self.widgets["mode_radio"].on_clicked(self.on_mode_change)

        self._install_key_handler()
        self.build_ui()
        self.draw_plot()
        plt.show(block=False)

    # ------------------------------------------------------------------ setup
    def _panel_axes(self) -> Any:
        """Create a frameless axes in the control column (placed later)."""
        ax = self.fig.add_axes((PANEL_X, 0.5, PANEL_W, 0.05))
        self._style_panel(ax)
        return ax

    @staticmethod
    def _style_panel(ax: Any, title: str = "") -> None:
        ax.set_facecolor(PANEL_COLOUR)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_xticks([])
        ax.set_yticks([])
        InteractivePlotWindow._set_header(ax, title)

    @staticmethod
    def _set_header(ax: Any, title: str) -> None:
        if title:
            ax.set_title(
                title,
                loc="left",
                fontsize=8.5,
                fontweight="bold",
                color=MUTED_COLOUR,
                pad=3,
            )

    def _install_key_handler(self) -> None:
        """Route our shortcut keys to the window, the rest to matplotlib."""
        canvas = self.fig.canvas
        manager = canvas.manager
        handler_id = getattr(manager, "key_press_handler_id", None)
        if handler_id is not None:
            canvas.mpl_disconnect(handler_id)
        canvas.mpl_connect("key_press_event", self.on_key)
        canvas.mpl_connect("scroll_event", self.on_scroll)
        canvas.mpl_connect("button_press_event", self.on_list_click)

    def on_key(self, event: KeyEvent) -> None:
        """Keyboard shortcuts; anything else gets matplotlib's default keys."""
        if event.key == "l":
            self.on_log_toggle(LOG_SCALE)
            self._sync_option_checks()
        elif event.key == "m":
            modes = list(PlotMode)
            self.on_mode_change(modes[(modes.index(self.mode) + 1) % len(modes)])
        elif event.key == "n":
            self.select_latest(None)
        elif event.key == "u":
            self.unselect_all(None)
        else:
            key_press_handler(event, self.fig.canvas, self.fig.canvas.toolbar)

    # -------------------------------------------------------------- selection
    def submit_scan(self, text: str) -> None:
        """Add a scan ID from the text box to the active scans and redraw."""
        if not text or text.startswith("Not found:"):
            return
        s_id = text.strip()
        if s_id in self.data_source:
            self.active_scans.add(s_id)
            self.reveal_scan(s_id)
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
        """Clear all active scan selections and redraw."""
        self.active_scans.clear()
        self.build_ui()
        self.draw_plot()

    def select_latest(self, event: Any) -> None:
        """Show only the most recent scan."""
        self._sync_scans()
        self.active_scans = {self.scans[-1]} if self.scans else set()
        self.build_ui()
        self.draw_plot()

    def _sync_scans(self) -> bool:
        """Align scan bookkeeping with ``data_source``.

        New scans are appended and selected (replacing the selection when
        ``follow_latest`` is on). If scans were removed or replaced under the
        same id, the list is rebuilt: stale selections are dropped and the new
        scans are selected. Returns True if anything changed.
        """
        keys = list(self.data_source.keys())
        replaced = {
            s
            for s in self.scans
            if s in self.data_source
            and self.data_source[s] is not self._scan_refs.get(s)
        }
        if keys[: len(self.scans)] == self.scans and not replaced:
            new = keys[len(self.scans) :]
            if not new:
                return False
            self.scans.extend(new)
            if self.follow_latest:
                self.active_scans = {new[-1]}
            else:
                self.active_scans.update(new)
            self._scan_refs.update({s: self.data_source[s] for s in new})
            return True

        kept = set(self.scans) & set(keys) - replaced
        new = [s for s in keys if s not in kept]
        self.scans = keys
        if self.follow_latest and new:
            self.active_scans = {new[-1]}
        else:
            self.active_scans = {s for s in self.active_scans if s in kept} | set(new)
        if not self.active_scans and keys:
            self.active_scans.add(keys[-1])
        self._scan_refs = {s: self.data_source[s] for s in keys}
        self.last_seen_points = {
            k: v for k, v in self.last_seen_points.items() if k in kept
        }
        return True

    def _ordered_active_scans(self) -> list[Any]:
        """Active scans in acquisition order (stable legend and colours)."""
        order = {s: i for i, s in enumerate(self.scans)}
        return sorted(
            (s for s in self.active_scans if s in self.data_source),
            key=lambda s: order.get(s, len(order)),
        )

    def scan_colour(self, s_id: Any) -> Any:
        """Colour of a scan; stays the same while the window is open."""
        try:
            index = self.scans.index(s_id)
        except ValueError:
            index = len(self.scans)
        return SCAN_COLOURS[index % len(SCAN_COLOURS)]

    def get_active_fields(self) -> list[str]:
        """Return a sorted list of all data fields across active scans."""
        fields = set()
        for s_id in self.active_scans:
            fields.update(self.data_source.get(s_id, {}).keys())
        fields -= SCALAR_META_FIELDS
        device_fields = sorted(fields - set(DERIVED_Y_FIELDS))
        derived_fields = [f for f in DERIVED_Y_FIELDS if f in fields]
        return device_fields + derived_fields

    def get_visible_scans(self) -> list[Any]:
        """Return the scans currently shown in the (scrollable) scan list."""
        offset = self._scan_list_offset()
        return self.scans[offset : offset + MAX_VISIBLE_SCANS]

    def _max_scan_offset(self) -> int:
        return max(0, len(self.scans) - MAX_VISIBLE_SCANS)

    def _scan_list_offset(self) -> int:
        """First visible row; follows the newest scans unless scrolled away."""
        if self.scan_offset is None:
            return self._max_scan_offset()
        return min(max(self.scan_offset, 0), self._max_scan_offset())

    def _set_scan_offset(self, offset: int) -> None:
        """Scroll the list; reaching the bottom resumes following new scans."""
        offset = min(max(offset, 0), self._max_scan_offset())
        self.scan_offset = None if offset >= self._max_scan_offset() else offset

    def scroll_scans(self, rows: int) -> None:
        """Scroll the scan list by ``rows`` (negative = towards older scans)."""
        self.scroll_list("scan", rows)

    def reveal_scan(self, s_id: Any) -> None:
        """Scroll the scan list so ``s_id`` is visible."""
        if s_id not in self.scans or s_id in self.get_visible_scans():
            return
        index = self.scans.index(s_id)
        offset = self._scan_list_offset()
        if index < offset:
            self._set_scan_offset(index)
        else:
            self._set_scan_offset(index - MAX_VISIBLE_SCANS + 1)

    # --------------------------------------------------------- scrolling lists
    def _list_axes(self) -> dict[str, Any]:
        """Scrollable lists currently on screen, by name."""
        lists = {"scan": self.ax_scan, "x": self.ax_x, "y": self.ax_y}
        if self._is_2d():
            lists["z"] = self.ax_z
        return lists

    def _list_items(self, name: str) -> list[Any]:
        """Every entry of a list, scrolled or not."""
        if name == "scan":
            return list(self.scans)
        if self._is_2d():
            return self.get_2d_fields() or [NO_FIELDS]
        fields = self.get_active_fields()
        if name == "x":
            return [POINT_NUMBER] + [f for f in fields if f not in DERIVED_Y_FIELDS]
        if name == "y":
            return fields
        return []

    @staticmethod
    def _list_capacity(name: str) -> int:
        return MAX_VISIBLE_SCANS if name == "scan" else MAX_VISIBLE_CHANNELS

    def _list_offset(self, name: str) -> int:
        if name == "scan":
            return self._scan_list_offset()
        n = len(self._list_items(name))
        top = max(0, n - self._list_capacity(name))
        return min(max(self.list_offsets.get(name, 0), 0), top)

    def _list_window(self, name: str) -> list[Any]:
        """The entries of a list that are currently visible."""
        offset = self._list_offset(name)
        return self._list_items(name)[offset : offset + self._list_capacity(name)]

    def _set_list_offset(self, name: str, offset: int) -> None:
        if name == "scan":
            self._set_scan_offset(offset)
        else:
            n = len(self._list_items(name))
            top = max(0, n - self._list_capacity(name))
            self.list_offsets[name] = min(max(offset, 0), top)

    def scroll_list(self, name: str, rows: int) -> None:
        """Scroll a list by ``rows`` (negative = up); redraw only that list."""
        before = self._list_window(name)
        self._set_list_offset(name, self._list_offset(name) + rows)
        if self._list_window(name) != before:
            self._build_list(name)
            self.fig.canvas.draw_idle()

    def _list_under(self, event: Any) -> str | None:
        for name, ax in self._list_axes().items():
            if event.inaxes is ax:
                return name
        return None

    def on_scroll(self, event: Any) -> None:
        """The mouse wheel scrolls whichever list it is over."""
        name = self._list_under(event)
        if name is None:
            return
        step = getattr(event, "step", 0) or (1 if event.button == "up" else -1)
        self.scroll_list(name, -1 if step > 0 else 1)

    def on_list_click(self, event: Any) -> None:
        """Clicking a list's scroll track jumps the list to that position."""
        name = self._list_under(event)
        if name is None:
            return
        n = len(self._list_items(name))
        capacity = self._list_capacity(name)
        if n <= capacity:
            return
        ax = self._list_axes()[name]
        x, y = ax.transAxes.inverted().transform((event.x, event.y))
        if x < SCROLLBAR_X:
            return
        # Top of the track is the first entry.
        self._set_list_offset(name, round((1.0 - y) * n - capacity / 2))
        self._build_list(name)
        self.fig.canvas.draw_idle()

    def _off_screen_note(self, name: str) -> str:
        """Header note for a selection that is scrolled out of view."""
        window = self._list_window(name)
        if name == "scan":
            hidden = len([s for s in self.active_scans if s not in window])
            return f"+{hidden} selected" if hidden else ""
        if name == "y" and not self._is_2d():
            hidden = len(
                [f for f, on in self.active_y_states.items() if on and f not in window]
            )
            return f"+{hidden} ticked" if hidden else ""
        selected = self._list_selection(name)
        if selected is None or selected in window:
            return ""
        if len(selected) > HEADER_NAME_CHARS:
            selected = selected[: HEADER_NAME_CHARS - 1] + "\u2026"
        return selected

    def _list_selection(self, name: str) -> str | None:
        """The single selected entry of a radio list."""
        if self._is_2d():
            return {"x": self.x_field, "y": self.y_field, "z": self.z_field}.get(name)
        return self.line_x if name == "x" else None

    def _list_header(self, name: str) -> str:
        base = {
            "scan": "SCANS",
            "x": "X" if self._is_2d() else "X AXIS",
            "y": "Y" if self._is_2d() else "Y CHANNELS",
            "z": "Z (colour)",
        }[name]
        n = len(self._list_items(name))
        capacity = self._list_capacity(name)
        if n <= capacity:
            return base
        first = self._list_offset(name) + 1
        header = f"{base}  {first}\u2013{first + capacity - 1}/{n}"
        note = self._off_screen_note(name)
        return f"{header}  \u00b7 {note}" if note else header

    def _scan_list_header(self) -> str:
        return self._list_header("scan")

    def _refresh_list_header(self, name: str) -> None:
        ax = self._list_axes().get(name)
        if ax is not None:
            self._set_header(ax, self._list_header(name))

    def _build_list(self, name: str) -> None:
        {
            "scan": self._build_scan_list,
            "x": self._build_x_list,
            "y": self._build_y_list,
            "z": self._build_z_list,
        }[name]()

    def _build_scan_list(self) -> None:
        """(Re)build only the scan checkboxes, e.g. after scrolling."""
        self._clear_widgets("scan_check")
        self.ax_scan.cla()
        self._style_panel(self.ax_scan, self._list_header("scan"))
        vis_scans = self.get_visible_scans()
        self.widgets["scan_check"] = self._check_buttons(
            self.ax_scan,
            [str(s) for s in vis_scans],
            [s in self.active_scans for s in vis_scans],
            colours=[self.scan_colour(s) for s in vis_scans],
        )
        self.widgets["scan_check"].on_clicked(self.on_scan_toggle)
        self._draw_scrollbar("scan")

    def _draw_scrollbar(self, name: str = "scan") -> None:
        """Thin track and thumb at the right of a list when it scrolls."""
        n = len(self._list_items(name))
        capacity = self._list_capacity(name)
        if n <= capacity:
            return
        ax = self._list_axes()[name]
        thumb_top = 1.0 - self._list_offset(name) / n
        thumb_h = capacity / n
        for y, h, colour in (
            (0.0, 1.0, SCROLL_TRACK_COLOUR),
            (thumb_top - thumb_h, thumb_h, SCROLL_THUMB_COLOUR),
        ):
            ax.add_patch(
                Rectangle(
                    (SCROLLBAR_X, y),
                    SCROLLBAR_W,
                    h,
                    transform=ax.transAxes,
                    facecolor=colour,
                    edgecolor="none",
                    clip_on=False,
                )
            )

    def _radio_list(
        self, name: str, widget_key: str, callback: Callable[[Any], Any]
    ) -> None:
        """Build a scrolled radio list showing the stored selection."""
        ax = self._list_axes()[name]
        self._clear_widgets(widget_key)
        ax.cla()
        self._style_panel(ax, self._list_header(name))
        window = self._list_window(name)
        selected = self._list_selection(name)
        in_view = selected in window
        radio = self._radio_buttons(
            ax, window, window.index(selected) if in_view else 0
        )
        if not in_view:
            # The selection is scrolled away: show no button as selected.
            buttons = getattr(radio, "_buttons", None)
            if buttons is not None:
                buttons.set_facecolor(["none"] * len(window))
        radio.on_clicked(callback)
        self.widgets[widget_key] = radio
        self._draw_scrollbar(name)

    def _build_x_list(self) -> None:
        self._radio_list("x", "radio_x", self.on_x_change)

    def _build_y_list(self) -> None:
        if self._is_2d():
            self._radio_list("y", "radio_y", self.on_y_change)
            return
        self._clear_widgets("check_y")
        self.ax_y.cla()
        self._style_panel(self.ax_y, self._list_header("y"))
        window = self._list_window("y")
        self.widgets["check_y"] = self._check_buttons(
            self.ax_y, window, [self.active_y_states.get(f, False) for f in window]
        )
        self.widgets["check_y"].on_clicked(self.on_y_toggle)
        self._draw_scrollbar("y")

    def _build_z_list(self) -> None:
        if self._is_2d():
            self._radio_list("z", "radio_z", self.on_z_change)

    def get_2d_scan(self) -> Any | None:
        """Return the most recent active scan ID for 2D plotting, or None."""
        if not self.active_scans:
            return None
        n_scans = len(self.scans)
        return max(
            self.active_scans,
            key=lambda s: self.scans.index(s) if s in self.scans else n_scans,
        )

    def get_2d_fields(self) -> list[str]:
        """Return the available field names for the current 2D scan."""
        s_id = self.get_2d_scan()
        if s_id is None:
            return []
        excluded = SCALAR_META_FIELDS | set(DERIVED_Y_FIELDS)
        scan = self.data_source.get(s_id, {})
        return [k for k in scan.keys() if k not in excluded]

    # ------------------------------------------------------------------ layout
    def _clear_widgets(self, *names: str) -> None:
        """Remove and disconnect the specified Matplotlib widgets."""
        for name in names:
            widget = self.widgets.pop(name, None)
            disconnect = getattr(widget, "disconnect_events", None)
            if disconnect is not None:
                disconnect()

    def _is_2d(self) -> bool:
        return self.mode in (PlotMode.GRID_2D, PlotMode.CONTOUR_2D)

    def _control_sections(self) -> list[tuple[Any, str, float]]:
        """The control column, top to bottom: (axes, header, rows or height)."""

        def rows(name: str) -> int:
            return max(1, len(self._list_window(name)))

        sections: list[tuple[Any, str, float]] = [
            (self.ax_scan_txt, "ADD SCAN (id + Enter)", -TEXTBOX_H),
            (self.ax_scan, self._list_header("scan"), rows("scan")),
            (self.ax_scan_btn, "", -BUTTON_H),
            # Short fixed lists keep full-size rows; only long lists shrink.
            (self.ax_mode, "PLOT MODE", -len(PlotMode) * MAX_ROW_H),
            (self.ax_log, "OPTIONS", -2 * MAX_ROW_H),
            (self.ax_x, self._list_header("x"), rows("x")),
            (self.ax_y, self._list_header("y"), rows("y")),
        ]
        if self._is_2d():
            sections.append((self.ax_z, self._list_header("z"), rows("z")))
        return sections

    def _apply_layout(self) -> None:
        """Stack the controls to fit the column and place the plot axes.

        Lists get a row height that fits the available space, so long channel
        lists shrink rather than overflow.
        """
        sections = self._control_sections()
        fixed = sum(-size for _, _, size in sections if size < 0)
        rows = sum(size for _, _, size in sections if size > 0)
        n_headers = sum(1 for _, header, _ in sections if header)
        available = (
            PANEL_TOP
            - PANEL_BOTTOM
            - fixed
            - n_headers * HEADER_H
            - (len(sections) - 1) * SECTION_GAP
        )
        self._row_h = min(MAX_ROW_H, available / rows) if rows else MAX_ROW_H

        top = PANEL_TOP
        for ax, header, size in sections:
            if header:
                top -= HEADER_H
            height = -size if size < 0 else size * self._row_h
            if ax is self.ax_scan_btn:
                half = (PANEL_W - 0.01) / 2
                self.ax_latest_btn.set_position((PANEL_X, top - height, half, height))
                ax.set_position((PANEL_X + half + 0.01, top - height, half, height))
            else:
                ax.set_position((PANEL_X, top - height, PANEL_W, height))
            top -= height + SECTION_GAP

        if self._is_2d():
            self.ax.set_position((0.07, 0.11, 0.57, 0.82))
            self.ax_cbar.set_position((0.655, 0.11, 0.016, 0.82))
            self.ax_cbar.set_visible(True)
            self.ax_z.set_visible(True)
        else:
            self.ax.set_position((0.07, 0.11, 0.60, 0.82))
            self.ax_cbar.cla()
            self.ax_cbar.set_visible(False)
            self.ax_z.cla()
            self._style_panel(self.ax_z)
            self.ax_z.set_visible(False)
        self.ax_d.set_position(self.ax.get_position())

    def _list_fontsize(self) -> float:
        return 9.0 if self._row_h >= 0.024 else (8.0 if self._row_h >= 0.017 else 6.5)

    def _check_buttons(
        self,
        ax: Any,
        labels: list[str],
        actives: list[bool],
        colours: list[Any] | None = None,
        fontsize: float | None = None,
    ) -> CheckButtons:
        size = fontsize if fontsize is not None else self._list_fontsize()
        label_props: dict[str, Any] = {"fontsize": [size] * len(labels)}
        if colours is not None:
            label_props["color"] = colours
        return _styled(
            CheckButtons,
            ax,
            labels,
            actives=actives,
            label_props=label_props,
            frame_props={"edgecolor": MUTED_COLOUR, "facecolor": "white"},
            check_props={"facecolor": ACCENT_COLOUR},
        )

    def _radio_buttons(self, ax: Any, labels: list[str], active: int) -> RadioButtons:
        return _styled(
            RadioButtons,
            ax,
            labels,
            active=active,
            activecolor=ACCENT_COLOUR,
            label_props={"fontsize": [self._list_fontsize()] * len(labels)},
        )

    def build_ui(self) -> None:
        """Rebuild interactive widgets for the current scans and plot mode."""
        self._sync_scans()
        self._clear_widgets(
            "scan_check", "check_log", "radio_x", "check_y", "radio_y", "radio_z"
        )
        for ax in (self.ax_scan, self.ax_log, self.ax_x, self.ax_y, self.ax_z):
            ax.cla()

        if self._is_2d():
            self._resolve_2d_fields(self.get_2d_fields())
        else:
            self._sync_line_selection()

        self._apply_layout()
        # The text box and buttons keep their own colours; only add headers.
        own_colours = (self.ax_scan_txt, self.ax_scan_btn)
        for ax, header, _ in self._control_sections():
            if ax in own_colours:
                self._set_header(ax, header)
            else:
                self._style_panel(ax, header)

        self._build_scan_list()

        self.widgets["check_log"] = self._check_buttons(
            self.ax_log,
            [LOG_SCALE, FOLLOW_LATEST],
            [self.log_scale, self.follow_latest],
            fontsize=9.0,
        )
        self.widgets["check_log"].on_clicked(self.on_option_toggle)

        self._build_x_list()
        self._build_y_list()
        self._build_z_list()

    def _sync_line_selection(self) -> None:
        """Keep the 1D x axis and ticked channels valid for the active fields."""
        fields = self.get_active_fields()
        if self.line_x not in self._list_items("x"):
            self.line_x = POINT_NUMBER

        new_active_y = {}
        for i, f in enumerate(fields):
            if f in self.active_y_states:
                new_active_y[f] = self.active_y_states[f]
            else:
                new_active_y[f] = i == 0 and not any(self.active_y_states.values())
        self.active_y_states.clear()
        self.active_y_states.update(new_active_y)

    def _resolve_2d_fields(self, fields: list[str]) -> None:
        """Set default X, Y, and Z fields for 2D plotting if unset or invalid."""
        if not fields:
            # A selected scan with no data yet keeps the user's previous choice.
            if self.get_2d_scan() is None:
                self.x_field = self.y_field = self.z_field = None
            return

        candidates = [f for f in fields if f != POINT_NUMBER] or fields
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

    # ---------------------------------------------------------------- events
    def on_mode_change(self, label: str | None) -> None:
        """Handle plot mode radio button selection changes."""
        if label is None or label == self.mode:
            return
        try:
            self.mode = PlotMode(label)
        except ValueError:
            return
        self._sync_mode_radio()
        self.build_ui()
        self.draw_plot()

    def _sync_mode_radio(self) -> None:
        """Show the current mode in the radio (e.g. after a key press)."""
        radio = self.widgets.get("mode_radio")
        if radio is None or radio.value_selected == self.mode:
            return
        radio.eventson = False
        try:
            radio.set_active(list(PlotMode).index(self.mode))
        finally:
            radio.eventson = True

    def _sync_option_checks(self) -> None:
        """Show the current options in the checkboxes (e.g. after a key press)."""
        checks = self.widgets.get("check_log")
        if checks is None:
            return
        wanted = [self.log_scale, self.follow_latest]
        checks.eventson = False
        try:
            for index, (shown, want) in enumerate(
                zip(checks.get_status(), wanted, strict=True)
            ):
                if shown != want:
                    checks.set_active(index)
        finally:
            checks.eventson = True

    def on_option_toggle(self, label: str | None) -> None:
        """Handle the Options checkboxes."""
        if label == LOG_SCALE:
            self.on_log_toggle(label)
        elif label == FOLLOW_LATEST:
            self.follow_latest = not self.follow_latest
            if self.follow_latest:
                self.select_latest(None)

    def on_log_toggle(self, label: str | None) -> None:
        """Toggle logarithmic scaling on or off and redraw the plot."""
        if label == LOG_SCALE:
            self.log_scale = not self.log_scale
            self.draw_plot()

    def on_x_change(self, label: str | None) -> None:
        """Handle X-axis field selection changes and redraw the plot."""
        if label not in (None, NO_FIELDS):
            if self._is_2d():
                self.x_field = label
            else:
                self.line_x = label
            self._refresh_list_header("x")
        self.draw_plot()

    def on_y_change(self, label: str | None) -> None:
        """Handle Y-axis field selection changes in 2D mode and redraw."""
        if label not in (None, NO_FIELDS):
            self.y_field = label
            self._refresh_list_header("y")
        self.draw_plot()

    def on_z_change(self, label: str | None) -> None:
        """Handle Z-axis field selection changes in 2D mode and redraw."""
        if label not in (None, NO_FIELDS):
            self.z_field = label
            self._refresh_list_header("z")
        self.draw_plot()

    def on_y_toggle(self, label: str | None) -> None:
        """Toggle visibility of a Y channel in 1D mode and redraw."""
        if label is not None:
            self.active_y_states[label] = not self.active_y_states.get(label, False)
            self._refresh_list_header("y")
        self.draw_plot()

    def on_scan_toggle(self, label: str | None) -> None:
        """Toggle whether a scan ID is active and update the UI and plot."""
        if label is None:
            return

        for s in self.get_visible_scans() + self.scans:
            if str(s) == label:
                if s in self.active_scans:
                    self.active_scans.remove(s)
                else:
                    self.active_scans.add(s)
                break
        self.build_ui()
        self.draw_plot()

    # --------------------------------------------------------------- drawing
    def draw_plot(self) -> None:
        """Render the plot according to the currently selected plot mode."""
        self._sync_scans()
        if self.mode == PlotMode.GRID_2D:
            self._draw_2d()
        elif self.mode == PlotMode.CONTOUR_2D:
            self._draw_contour()
        else:
            self._draw_1d()
        self._update_status()

    @staticmethod
    def _style_plot_axes(ax: Any, grid: bool = True) -> None:
        ax.set_facecolor("white")
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(MUTED_COLOUR)
        ax.tick_params(colors=TEXT_COLOUR, labelsize=9)
        ax.xaxis.label.set_color(TEXT_COLOUR)
        ax.yaxis.label.set_color(TEXT_COLOUR)
        if grid:
            ax.grid(True, color=GRID_COLOUR, linewidth=0.7)
            ax.set_axisbelow(True)

    @staticmethod
    def _n_points(s_data: dict[str, list[Any]]) -> int:
        first_key = next(iter(s_data.keys()), None)
        return len(s_data[first_key]) if first_key is not None else 0

    def _plot_title(self, scans: list[Any], channels: list[str]) -> str:
        if not scans:
            return "No scan selected"
        shown = ", ".join(str(s) for s in scans[:4])
        more = f" +{len(scans) - 4}" if len(scans) > 4 else ""
        prefix = "Scan" if len(scans) == 1 else "Scans"
        title = f"{prefix} {shown}{more}"
        if channels:
            title += "  ·  " + ", ".join(channels[:3])
            if len(channels) > 3:
                title += f" +{len(channels) - 3}"
        return title

    def _update_status(self) -> None:
        """One-line summary under the plot: newest scan, points, last update."""
        scans = self._ordered_active_scans()
        if not scans:
            text = "Select a scan on the right, or type its id."
        else:
            newest = scans[-1]
            n_pts = self._n_points(self.data_source[newest])
            text = (
                f"Scan {newest}: {n_pts} point{'s' if n_pts != 1 else ''}"
                f"   ·   {len(scans)} scan{'s' if len(scans) != 1 else ''} shown"
                f"   ·   updated {time.strftime('%H:%M:%S')}"
            )
        self._status_text.set_text(text)

    def _draw_1d(self) -> None:
        """Render 1D line plots for all active scans and selected Y channels.

        Each scan has its own colour and each channel its own line style. The
        fitted Gaussian is dashed in the scan's colour with its centre marked,
        and derivatives go on a right-hand axis.
        """
        self.ax.cla()
        self.ax_d.cla()
        self.ax_d.set_visible(False)
        self._style_plot_axes(self.ax)

        scans = self._ordered_active_scans()
        x_choice = self.line_x
        if x_choice != POINT_NUMBER and any(
            x_choice not in self.data_source[s_id] for s_id in scans
        ):
            x_choice = POINT_NUMBER

        selected = [f for f, on in self.active_y_states.items() if on]
        data_channels = [f for f in selected if f not in DERIVED_Y_FIELDS]
        style_of = {
            f: CHANNEL_LINESTYLES[i % len(CHANNEL_LINESTYLES)]
            for i, f in enumerate(data_channels)
        }

        handles: list[Any] = []
        for s_id in scans:
            s_data = self.data_source[s_id]
            colour = self.scan_colour(s_id)
            n_pts = self._n_points(s_data)
            if x_choice == POINT_NUMBER or x_choice not in s_data:
                x_vals = np.arange(1, n_pts + 1, dtype=float)
            else:
                x_vals = _as_floats(s_data[x_choice])

            for y_field in selected:
                if y_field not in s_data:
                    continue
                y_vals = _as_floats(s_data[y_field])
                n = min(len(x_vals), len(y_vals))
                label = f"{s_id}: {y_field}"
                if y_field in DERIVATIVE_FIELDS:
                    (line,) = self.ax_d.plot(
                        x_vals[:n],
                        y_vals[:n],
                        color=colour,
                        linestyle=":" if y_field == FIT_D1 else "-.",
                        linewidth=1.2,
                        label=label,
                    )
                    self.ax_d.set_visible(True)
                elif y_field == FIT_GAUSSIAN:
                    (line,) = self.ax.plot(
                        x_vals[:n],
                        y_vals[:n],
                        color=colour,
                        linestyle="--",
                        linewidth=1.3,
                        alpha=0.9,
                        label=label,
                    )
                    self._mark_centre(s_data, colour, x_choice)
                else:
                    (line,) = self.ax.plot(
                        x_vals[:n],
                        y_vals[:n],
                        color=colour,
                        linestyle=style_of[y_field],
                        linewidth=1.6,
                        marker="o" if n <= MARKER_POINT_LIMIT else None,
                        markersize=3.5,
                        label=label,
                    )
                handles.append(line)

        self.ax.set_xlabel(x_choice)
        if len(data_channels) == 1:
            self.ax.set_ylabel(data_channels[0])
        self.ax.set_title(
            self._plot_title(scans, data_channels or selected),
            loc="left",
            fontsize=11,
            color=TEXT_COLOUR,
        )
        if self.ax_d.get_visible():
            # cla() resets a twin axis to the left; put it back on the right.
            self.ax_d.yaxis.tick_right()
            self.ax_d.yaxis.set_label_position("right")
            self.ax_d.set_ylabel("derivative", color=MUTED_COLOUR)
            self.ax_d.tick_params(colors=MUTED_COLOUR, labelsize=8.5)
            for side in ("top", "left", "bottom"):
                self.ax_d.spines[side].set_visible(False)
        if handles:
            self.ax.legend(
                handles=handles,
                loc="best" if len(handles) <= 8 else "upper left",
                fontsize=8,
                ncol=1 if len(handles) <= 8 else 2,
                frameon=True,
                framealpha=0.9,
                edgecolor=GRID_COLOUR,
            )
        elif not scans:
            self._show_hint("Select a scan on the right to plot it.")
        else:
            self._show_hint("Tick a Y channel to plot it.")

        if self.log_scale and self._has_positive(scans, selected):
            self.ax.set_yscale("log")
        else:
            self.ax.set_yscale("linear")
        self.fig.canvas.draw_idle()

    def _has_positive(self, scans: list[Any], fields: list[str]) -> bool:
        return any(
            (number := to_float(v)) is not None and number > 0
            for s_id in scans
            for y_field in fields
            if y_field not in DERIVATIVE_FIELDS
            for v in self.data_source[s_id].get(y_field, [])
        )

    def _mark_centre(
        self, s_data: dict[str, list[Any]], colour: Any, x_choice: str
    ) -> None:
        """Mark the fitted centre on the x axis (only when x is a real axis)."""
        centre = s_data.get(FIT_CENTRE)
        if x_choice == POINT_NUMBER or not centre:
            return
        value = to_float(centre[0])
        if value is None:
            return
        self.ax.axvline(value, color=colour, linestyle=":", linewidth=1.0)
        self.ax.annotate(
            f"{value:.4g}",
            xy=(value, 1.0),
            xycoords=("data", "axes fraction"),
            xytext=(3, -12),
            textcoords="offset points",
            fontsize=8,
            color=colour,
        )

    def _show_hint(self, text: str) -> None:
        self.ax.text(
            0.5,
            0.5,
            text,
            transform=self.ax.transAxes,
            ha="center",
            va="center",
            fontsize=10,
            color=MUTED_COLOUR,
        )

    def _get_2d_norm(self, zs: list[float]) -> Any:
        """Return a LogNorm for positive Z values if log scale is on, else None."""
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
        """Prepare axes, extract XYZ data, and render a 2D plot with colorbar.

        The newest point is ringed so progress through the scan is visible.
        """
        self.ax.cla()
        self.ax_d.cla()
        self.ax_d.set_visible(False)
        self.ax_cbar.cla()
        self.ax_cbar.set_visible(False)
        self._style_plot_axes(self.ax, grid=False)

        s_id = self.get_2d_scan()
        if s_id is None:
            self.ax.set_title(f"{self.mode}: no scan selected", loc="left")
            self._show_hint("Select a scan on the right to plot it.")
            self.fig.canvas.draw_idle()
            return

        xs, ys, zs = extract_xyz(
            self.data_source[s_id], self.x_field, self.y_field, self.z_field
        )

        self.ax.set_xlabel(self.x_field or "")
        self.ax.set_ylabel(self.y_field or "")
        if not xs:
            self.ax.set_title(f"Scan {s_id}: waiting for data", loc="left")
            self._show_hint("Waiting for the first points...")
            self.fig.canvas.draw_idle()
            return

        norm = self._get_2d_norm(zs)
        mappable = render_fn(xs, ys, zs, norm)
        self.ax.plot(
            xs[-1],
            ys[-1],
            marker="o",
            markersize=10,
            markerfacecolor="none",
            markeredgecolor=LIVE_COLOUR,
            markeredgewidth=1.8,
            linestyle="none",
            zorder=5,
            clip_on=False,
        )

        self.ax_cbar.set_visible(True)
        colorbar = self.fig.colorbar(mappable, cax=self.ax_cbar)
        if isinstance(norm, LogNorm):
            # Contour levels are not round numbers; label decades instead so
            # long tick labels do not push the colour-bar label off the plot.
            colorbar.locator = LogLocator()
            colorbar.formatter = LogFormatterSciNotation()
            colorbar.update_ticks()
        colorbar.set_label(self.z_field or "", color=TEXT_COLOUR)
        colorbar.outline.set_visible(False)
        self.ax_cbar.tick_params(labelsize=8.5, colors=TEXT_COLOUR)

        self.ax.set_title(
            f"Scan {s_id}  ·  {self.z_field}  ({len(xs)} points)",
            loc="left",
            fontsize=11,
            color=TEXT_COLOUR,
        )
        self.fig.canvas.draw_idle()

    def _render_heatmap(
        self, xs: list[float], ys: list[float], zs: list[float], norm: Any = None
    ) -> Any:
        """Render 2D data as a gridded heatmap, falling back to scatter."""
        heatmap = grid_heatmap(xs, ys, zs)
        if heatmap is not None:
            x_edges, y_edges, grid = heatmap
            return self.ax.pcolormesh(
                x_edges, y_edges, grid, cmap=self.cmap, shading="flat", norm=norm
            )
        return self.ax.scatter(
            xs, ys, c=zs, cmap=self.cmap, norm=norm, s=28, edgecolors="none"
        )

    def _render_contour(
        self, xs: list[float], ys: list[float], zs: list[float], norm: Any = None
    ) -> Any:
        """Render 2D data as a filled contour plot, falling back to scatter."""
        if norm is not None:
            pos_pts = [(x, y, z) for x, y, z in zip(xs, ys, zs, strict=True) if z > 0]
            if len(pos_pts) >= 3 and len({round(p[2], 6) for p in pos_pts}) > 1:
                cx, cy, cz = zip(*pos_pts, strict=False)
                try:
                    tri = Triangulation(cx, cy)
                    levels = np.geomspace(norm.vmin, norm.vmax, 15)
                    return self.ax.tricontourf(
                        tri, cz, levels=levels, cmap=self.cmap, norm=norm
                    )
                except Exception:
                    pass
        elif len(xs) >= 3 and len({round(v, 6) for v in zs}) > 1:
            try:
                tri = Triangulation(xs, ys)
                return self.ax.tricontourf(tri, zs, levels=15, cmap=self.cmap)
            except Exception:
                pass
        return self.ax.scatter(
            xs, ys, c=zs, cmap=self.cmap, norm=norm, s=28, edgecolors="none"
        )

    def _draw_2d(self) -> None:
        """Draw the 2D grid heatmap plot."""
        self._draw_2d_plot(self._render_heatmap)

    def _draw_contour(self) -> None:
        """Draw the 2D triangulated contour plot."""
        self._draw_2d_plot(self._render_contour)

    def update_plot(self) -> None:
        """Check for new scans, fields, or points and refresh the UI and plot."""
        if not plt.fignum_exists(self.fig.number):
            return

        added = self._sync_scans()

        current_fields = self.get_active_fields()
        current_2d_fields = self.get_2d_fields()
        fields_changed = (
            current_fields != self._last_seen_fields
            or current_2d_fields != self._last_seen_2d_fields
        )
        if fields_changed:
            self._last_seen_fields = current_fields
            self._last_seen_2d_fields = current_2d_fields

        needs_redraw = added or fields_changed
        for s_id in self.active_scans:
            n_pts = self._n_points(self.data_source[s_id])
            if self.last_seen_points.get(s_id, 0) != n_pts:
                self.last_seen_points[s_id] = n_pts
                needs_redraw = True

        if added or fields_changed:
            self.build_ui()

        if needs_redraw:
            self.draw_plot()
