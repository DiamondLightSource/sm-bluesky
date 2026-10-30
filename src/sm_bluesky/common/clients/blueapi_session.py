import json
import os
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any

import click
import matplotlib.pyplot as plt
from blueapi.client import BlueapiClient
from blueapi.client.event_bus import AnyEvent
from blueapi.config import ApplicationConfig
from blueapi.core import DataEvent
from lmfit.model import ModelResult

from sm_bluesky.common.math import (
    DerivativeResult,
    calculate_com,
    calculate_derivatives,
    fit_gaussian,
)

from .interactive_plot import DEFAULT_CMAP, InteractivePlotWindow


@dataclass
class FitResult:
    gaussian: ModelResult
    com: float
    df: DerivativeResult


class BlueAPISession:
    def __init__(
        self, config: ApplicationConfig, instrument_session: str | None = None
    ):
        self.config: ApplicationConfig = config
        self.data: dict[str, dict[str, list[Any]]] = {}
        self.current_scan_id: Any | None = None
        self._active_plot_windows: list[InteractivePlotWindow] = []
        self.auto_analyse: bool = True
        self.preferred_x: str | None = None
        self.preferred_y: str | None = None
        click.echo("Connecting to BlueAPI service...")
        self.bc = BlueapiClient.from_config(self.config)
        self.bc.login()

        self._install_callbacks()
        self.bc.run_task = self._live_plot_during_task(self.bc.run_task)
        self.print_inventory()

        if instrument_session:
            self.bc.instrument_session = instrument_session
            click.echo(f"Active instrument session: {instrument_session}")
            self._load_scan_cache()
        else:
            click.secho(
                "\n[Notice] No instrument session set. Set `bc.instrument_session ="
                " '<session_id>'` before dispatching plans.",
                fg="red",
            )

    def _get_cache_path(self) -> str | None:
        if not getattr(self.bc, "instrument_session", None):
            return None
        cache_dir = os.path.expanduser("~/.sm-bluesky/cache")
        os.makedirs(cache_dir, exist_ok=True)
        return os.path.join(cache_dir, f"{self.bc.instrument_session}_scans.jsonl")

    def _load_scan_cache(self) -> None:
        cache_file = self._get_cache_path()
        if not cache_file:
            return
        if not os.path.exists(cache_file):
            return

        try:
            with open(cache_file) as f:
                for line in f:
                    data_chunk = json.loads(line)
                    self.data.update(data_chunk)
            if self.data:
                click.echo(f"Loaded {len(self.data)} previous scans from cache.")
        except Exception as e:
            click.echo(f"Warning: Could not read scan cache: {e}")

    def _save_scan_to_cache(self, scan_id: str) -> None:
        cache_file = self._get_cache_path()
        if not cache_file or scan_id not in self.data:
            return

        try:
            with open(cache_file, "a") as f:
                line = json.dumps({str(scan_id): self.data[scan_id]})
                f.write(line + "\n")
        except Exception as e:
            click.echo(f"Warning: Could not write to scan cache: {e}")

    def start_shell(self) -> None:
        """Start an interactive IPython shell with the BlueAPI client available."""
        from IPython import start_ipython
        from traitlets.config import Config

        c = Config()
        c.InteractiveShellApp.exec_lines = [
            (
                "try:\n\tget_ipython().run_line_magic('matplotlib', 'auto')"
                "\n\tplot()\n"
                "except Exception as e:"
                "\n\tprint(f'Failed to start interactive plot: {e}')"
            )
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
                "show_plan": self.print_plans,
                "dev": self.bc.devices,
                "show_devices": self.print_devices,
                "scan_data": self.data,
                "plot": self.plot,
                "run": self.run,
                "fit_scan": self.fit_scan,
                "set_fit_axes": self.set_fit_axes,
            },
        )

    def _refresh_plots(self, update_data: bool = True) -> None:
        self._active_plot_windows = [
            win
            for win in self._active_plot_windows
            if plt.fignum_exists(win.fig.number)
        ]
        for win in self._active_plot_windows:
            if update_data:
                win.update_plot()
            win.fig.canvas.flush_events()

    def _live_plot_during_task(self, func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(func, *args, **kwargs)
            try:
                last_update = 0.0
                while not future.done():
                    now = time.monotonic()
                    should_update = (now - last_update) >= 1.0
                    if should_update:
                        last_update = now
                    self._refresh_plots(update_data=should_update)
                    time.sleep(0.18)
                self._refresh_plots(update_data=True)
                return future.result()
            finally:
                executor.shutdown(wait=False, cancel_futures=True)

        return wrapper

    def plot(self, scan_id: Any | None = None, cmap: str = DEFAULT_CMAP) -> None:
        """Open an interactive plot window for multiple scans and axes."""
        self._active_plot_windows = [
            win
            for win in self._active_plot_windows
            if plt.fignum_exists(win.fig.number)
        ]

        window = InteractivePlotWindow(self.data, scan_id, cmap=cmap)
        self._active_plot_windows.append(window)

    def set_fit_axes(self, x: str | None = None, y: str | None = None) -> None:
        """Set preferred X and Y channel names for fit_scan and auto-analysis."""
        self.preferred_x = x
        self.preferred_y = y

    def fit_scan(
        self,
        scan_id: Any | None = None,
        x: str | None = None,
        y: str | None = None,
        guess: Any | None = None,
    ) -> FitResult:
        """Perform Gaussian fit and Centre of Mass calculation on scan data."""
        if scan_id is None:
            scan_id = next(reversed(self.data))
        scan = self.data[str(scan_id)]
        x_col = x or (self.preferred_x if self.preferred_x in scan else None)
        y_col = y or (self.preferred_y if self.preferred_y in scan else None)
        vals = list(scan.values())
        if len(vals) >= 2:
            x_data = scan[x_col] if x_col else vals[0]
            y_data = scan[y_col] if y_col else vals[1]
        elif len(vals) == 1:
            y_data = scan[y_col] if y_col else vals[0]
            x_data = scan[x_col] if x_col else list(range(1, len(y_data) + 1))
        else:
            raise ValueError("Scan has no data")
        g_res = fit_gaussian(x_data, y_data, guess)
        com_res = calculate_com(x_data, y_data)
        df_res = calculate_derivatives(x_data, y_data)
        click.echo(
            f"Fit (scan {scan_id}): centre={g_res.best_values['center']:.4f}, "
            f"FWHM={g_res.params['fwhm'].value:.4f}, COM={com_res:.4f}"
        )
        return FitResult(gaussian=g_res, com=com_res, df=df_res)

    def print_plans(self) -> None:
        click.echo("\nPlans available:")
        for plan in self.bc.plans:
            click.echo(f"  {plan.name}")

    def print_devices(self) -> None:
        click.echo("\nDevices available:")
        for device in self.bc.devices:
            click.echo(f"  {device.name}")

    def print_inventory(self) -> None:
        self.print_plans()
        self.print_devices()

    def run(self, script: str | Path) -> None:
        """Execute a Python script inside the active session namespace."""
        from IPython.core.getipython import get_ipython

        script_path = Path(script).expanduser().resolve()
        if not script_path.is_file():
            click.secho(f"Error: Script not found: {script_path}", fg="red")
            return

        try:
            source = script_path.read_text()
            compile(source, str(script_path), "exec")
        except Exception as e:
            click.secho(f"Error in script {script_path}: {e}", fg="red")
            return

        ip = get_ipython()
        if ip is None:
            click.secho(
                f"Error: Cannot execute script {script_path}: No active session found.",
                fg="red",
            )
            return
        try:
            ip.run_line_magic("run", f'-i "{script_path}"')

        except Exception as e:
            click.secho(f"Error executing script {script_path}: {e}", fg="red")

    def _install_callbacks(self) -> None:
        """Install a callback to store the data events locally"""

        def feedback(event: AnyEvent) -> None:

            match event:
                case DataEvent(
                    name="start", doc={"scan_id": scan_id, "uid": uid, "time": time}
                ):
                    scan_id_str = str(scan_id)
                    idx = 1
                    while scan_id_str in self.data:
                        scan_id_str = f"{scan_id}_{idx}"
                        idx += 1
                    self.current_scan_id = scan_id_str
                    self.data[scan_id_str] = {}

                    click.echo(
                        f"{self._format_time(time)} -"
                        f" Run started (scan_id={scan_id_str}, uid={uid})"
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
                    if self.current_scan_id is not None:
                        self._save_scan_to_cache(str(self.current_scan_id))
                        if self.auto_analyse:
                            try:
                                fit_res = self.fit_scan(self.current_scan_id)
                                p_cen = fit_res.gaussian.best_values["center"]
                                com = fit_res.com
                                zc = fit_res.df.zero_crossings
                                self.data[self.current_scan_id].update(
                                    {
                                        "fit": fit_res.gaussian.best_fit.tolist(),
                                        "d1": fit_res.df.d1.tolist(),
                                        "d2": fit_res.df.d2.tolist(),
                                        "centre": [p_cen],
                                        "com": [com],
                                        "zero_crossing": zc,
                                        "max_slope_x": [fit_res.df.max_slope_x],
                                        "min_slope_x": [fit_res.df.min_slope_x],
                                    }
                                )

                            except Exception as e:
                                click.echo(f"Auto-fit failed: {e}")
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
