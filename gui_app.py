from __future__ import annotations

import queue
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk

from core.flow_runner import FlowRunner
from core.utils import ensure_dir, load_config, resolve_path

ICON_PATH = resolve_path("efore_favicon.ico")

# Professional industrial console palette
COLORS = {
    "bg": "#0f1419",
    "panel": "#1a2332",
    "panel_alt": "#243044",
    "border": "#2d3a4f",
    "text": "#e8eef7",
    "text_dim": "#8b9bb4",
    "accent": "#3b82f6",
    "accent_hover": "#2563eb",
    "success": "#22c55e",
    "warning": "#f59e0b",
    "danger": "#ef4444",
    "danger_hover": "#dc2626",
    "log_bg": "#0b1016",
    "btn_disabled_bg": "#334155",
    "btn_disabled_fg": "#64748b",
}


class QueueLogHandler:
    def __init__(self, q: queue.Queue[tuple[str, str]], log_file: Path | None = None):
        self.q = q
        self.log_file = log_file
        self._file_lock = threading.Lock()

    def _format(self, msg: str, *args) -> str:
        return (msg % args) if args else msg

    def _write(self, level: str, message: str) -> None:
        self.q.put((level, message))
        if self.log_file is None:
            return
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with self._file_lock, self.log_file.open("a", encoding="utf-8") as log:
                log.write(f"{timestamp} [{level.upper()}] {message}\n")
        except Exception:
            pass

    def info(self, msg: str, *args):
        self._write("info", self._format(msg, *args))

    def warning(self, msg: str, *args):
        self._write("warning", "WARN: " + self._format(msg, *args))

    def error(self, msg: str, *args):
        self._write("error", "ERROR: " + self._format(msg, *args))

    def debug(self, msg: str, *args):
        self._write("info", "DEBUG: " + self._format(msg, *args))

    def exception(self, msg: str, *args):
        self._write("error", "ERROR: " + self._format(msg, *args))


class App(tk.Tk):
    """Production GUI with professional industrial console styling."""

    def __init__(self):
        super().__init__()
        self.title("Bot tester for cabinet")
        self.configure(bg=COLORS["bg"])

        try:
            if ICON_PATH.exists():
                self.iconbitmap(str(ICON_PATH))
        except Exception:
            pass

        self.config_data = load_config("config/settings.yaml")
        ui_cfg = self.config_data.get("ui", {})
        initial_width = int(ui_cfg.get("initial_width", 1040))
        initial_height = int(ui_cfg.get("initial_height", 680))
        min_width = int(ui_cfg.get("min_width", 920))
        min_height = int(ui_cfg.get("min_height", 580))
        initial_x = ui_cfg.get("initial_x")
        initial_y = ui_cfg.get("initial_y")
        if initial_x is not None and initial_y is not None:
            x = int(initial_x)
            y = int(initial_y)
            try:
                screen_w = self.winfo_screenwidth()
                screen_h = self.winfo_screenheight()
                x = max(0, min(x, max(0, screen_w - initial_width)))
                y = max(0, min(y, max(0, screen_h - initial_height)))
            except Exception:
                pass
            self.geometry(f"{initial_width}x{initial_height}+{x}+{y}")
        else:
            self.geometry(f"{initial_width}x{initial_height}")
        self.minsize(min_width, min_height)

        files_cfg = self.config_data.get("files", {})
        ensure_dir(files_cfg.get("log_dir", "logs"))
        ensure_dir(files_cfg.get("screenshot_dir", "screenshots"))
        ensure_dir(files_cfg.get("trace_dir", "traces"))
        ensure_dir("debug/captcha_samples")

        log_dir = Path(files_cfg.get("log_dir", "logs"))
        self.log_file = log_dir / f"bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self.log_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.log_handler = QueueLogHandler(self.log_queue, self.log_file)

        self.runner = FlowRunner(self.config_data, self.log_handler, self._on_state_change)
        self._worker: threading.Thread | None = None
        self._state = "idle"

        self._fonts = self._init_fonts()
        self._build_ui()
        self.after(100, self._drain_logs)

        # Apply idle presentation size/opacity from settings.
        try:
            self.attributes("-alpha", float(ui_cfg.get("idle_alpha", 0.75)))
            self.attributes("-topmost", True)
        except Exception:
            pass

    def _init_fonts(self) -> dict:
        family = "Segoe UI"
        mono = "Consolas"
        try:
            available = set(tkfont.families())
            if "Microsoft YaHei UI" in available:
                family = "Microsoft YaHei UI"
            elif "Microsoft YaHei" in available:
                family = "Microsoft YaHei"
            if "Cascadia Mono" in available:
                mono = "Cascadia Mono"
            elif "Cascadia Code" in available:
                mono = "Cascadia Code"
        except Exception:
            pass
        return {
            "title": tkfont.Font(family=family, size=12, weight="bold"),
            "subtitle": tkfont.Font(family=family, size=9),
            "button": tkfont.Font(family=family, size=9, weight="bold"),
            "label": tkfont.Font(family=family, size=9),
            "status": tkfont.Font(family=family, size=9, weight="bold"),
            "log": tkfont.Font(family=mono, size=9),
        }

    def _build_ui(self):
        # Compact header for small-window professional layout
        header = tk.Frame(self, bg=COLORS["panel"])
        header.pack(fill="x", side="top")

        header_inner = tk.Frame(header, bg=COLORS["panel"])
        header_inner.pack(fill="x", padx=12, pady=(9, 7))

        top_row = tk.Frame(header_inner, bg=COLORS["panel"])
        top_row.pack(fill="x")

        title_col = tk.Frame(top_row, bg=COLORS["panel"])
        title_col.pack(side="left", fill="x", expand=True)
        tk.Label(
            title_col,
            text="Bot tester for cabinet",
            font=self._fonts["title"],
            fg=COLORS["text"],
            bg=COLORS["panel"],
            anchor="w",
        ).pack(anchor="w")
        tk.Label(
            title_col,
            text="Cabinet automation console",
            font=self._fonts["subtitle"],
            fg=COLORS["text_dim"],
            bg=COLORS["panel"],
            anchor="w",
        ).pack(anchor="w", pady=(0, 0))

        # Status badge with a small activity dot and a compact state label.
        self.status_box = tk.Frame(top_row, bg=COLORS["panel"])
        self.status_box.pack(side="right", anchor="n", pady=(1, 0))
        self.activity_dot = tk.Label(
            self.status_box,
            text="●",
            font=self._fonts["status"],
            fg="#9ca3af",
            bg=COLORS["panel"],
            padx=0,
            pady=0,
        )
        self.activity_dot.pack(side="left", padx=(0, 6))
        self.status_var = tk.StringVar(value="Idle")
        self.status_chip = tk.Label(
            self.status_box,
            textvariable=self.status_var,
            font=self._fonts["status"],
            fg="#e2e8f0",
            bg="#334155",
            padx=10,
            pady=4,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground="#475569",
            highlightcolor="#475569",
        )
        self.status_chip.pack(side="left")
        self.status_label = self.status_chip
        self.error_hint = tk.Label(
            self.status_box,
            text="",
            font=self._fonts["status"],
            fg="#bfdbfe",
            bg=COLORS["panel"],
            padx=0,
            pady=0,
        )
        self.error_hint.pack(side="left", padx=(6, 0))

        # Subtle divider under the hero block
        tk.Frame(header, bg="#1f2a3d", height=1).pack(fill="x")

        # Buttons row under header (equal-ish space for small window)
        toolbar = tk.Frame(self, bg=COLORS["bg"])
        toolbar.pack(fill="x", padx=12, pady=(10, 6))

        self.start_btn = self._make_action_button(
            toolbar, "Start", COLORS["success"], self.on_start
        )
        self.continue_btn = self._make_action_button(
            toolbar, "Continue", COLORS["accent"], self.on_continue
        )
        self.end_btn = self._make_action_button(
            toolbar, "End", COLORS["danger"], self.on_end, hover=COLORS["danger_hover"]
        )
        self.start_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.continue_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.end_btn.pack(side="left", fill="x", expand=True)

        # Log panel
        body = tk.Frame(self, bg=COLORS["bg"])
        body.pack(fill="both", expand=True, padx=12, pady=(4, 10))

        log_header = tk.Frame(body, bg=COLORS["panel_alt"])
        log_header.pack(fill="x")
        tk.Label(
            log_header,
            text="  Log",
            font=self._fonts["label"],
            fg=COLORS["text_dim"],
            bg=COLORS["panel_alt"],
            anchor="w",
            pady=5,
        ).pack(side="left", fill="x", expand=True)
        self.log_meta_var = tk.StringVar(value="")
        tk.Label(
            log_header,
            textvariable=self.log_meta_var,
            font=self._fonts["label"],
            fg=COLORS["text_dim"],
            bg=COLORS["panel_alt"],
            padx=8,
        ).pack(side="right")

        log_wrap = tk.Frame(body, bg=COLORS["border"], bd=0)
        log_wrap.pack(fill="both", expand=True)
        log_wrap.pack_propagate(False)

        self.log_text = tk.Text(
            log_wrap,
            wrap="word",
            font=self._fonts["log"],
            bg=COLORS["log_bg"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            selectbackground=COLORS["accent"],
            selectforeground=COLORS["text"],
            relief="flat",
            borderwidth=0,
            padx=12,
            pady=10,
            state="disabled",
        )
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        # Thumb-only scrollbar: no arrows, trough painted same as log (invisible track).
        style.layout(
            "Dark.Vertical.TScrollbar",
            [
                (
                    "Vertical.Scrollbar.trough",
                    {
                        "sticky": "ns",
                        "children": [
                            ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"}),
                        ],
                    },
                )
            ],
        )
        style.configure(
            "Dark.Vertical.TScrollbar",
            gripcount=0,
            background=COLORS["panel_alt"],
            darkcolor=COLORS["log_bg"],
            lightcolor=COLORS["log_bg"],
            troughcolor=COLORS["log_bg"],
            bordercolor=COLORS["log_bg"],
            arrowcolor=COLORS["log_bg"],
            relief="flat",
            borderwidth=0,
            arrowsize=0,
            width=8,
        )
        style.map(
            "Dark.Vertical.TScrollbar",
            background=[
                ("active", COLORS["accent"]),
                ("pressed", COLORS["accent_hover"]),
            ],
            troughcolor=[
                ("active", COLORS["log_bg"]),
                ("!disabled", COLORS["log_bg"]),
            ],
        )

        scroll = ttk.Scrollbar(
            log_wrap,
            orient="vertical",
            command=self.log_text.yview,
            style="Dark.Vertical.TScrollbar",
        )
        self.log_text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.log_text.pack(side="left", fill="both", expand=True)

        self.log_text.tag_configure("info", foreground="#94a3b8")
        self.log_text.tag_configure("warning", foreground=COLORS["warning"])
        self.log_text.tag_configure("error", foreground="#f87171")
        self.log_text.tag_configure("success", foreground=COLORS["success"])
        self.log_text.tag_configure("time", foreground=COLORS["text_dim"])

        # Footer
        footer = tk.Frame(self, bg=COLORS["panel"], height=28)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        self._refresh_buttons()
        self._append_log_line("info", "Console ready. Click START to begin automation.")

    def _make_action_button(self, parent, text, color, command, hover=None):
        hover = hover or COLORS["accent_hover"]
        btn = tk.Button(
            parent,
            text=text,
            font=self._fonts["button"],
            command=command,
            bg=color,
            fg="#ffffff",
            activebackground=hover,
            activeforeground="#ffffff",
            disabledforeground=COLORS["btn_disabled_fg"],
            relief="flat",
            bd=0,
            padx=14,
            pady=8,
            cursor="hand2",
            highlightthickness=0,
        )
        return btn

    def _style_button(self, btn: tk.Button, enabled: bool, enabled_bg: str):
        if enabled:
            btn.config(
                state="normal",
                bg=enabled_bg,
                fg="#ffffff",
                cursor="hand2",
            )
        else:
            btn.config(
                state="disabled",
                bg=COLORS["btn_disabled_bg"],
                fg=COLORS["btn_disabled_fg"],
                cursor="arrow",
            )

    def _status_color(self, state: str) -> str:
        s = (state or "").lower()
        if s in {"idle"}:
            return "#9ca3af"
        if s in {"starting", "running", "continue_running", "logged_in", "navigated"}:
            return "#60a5fa"
        if s in {"continue_done", "active_alarm_done", "download_upload_done", "south_comm_done", "calibration_done"}:
            return "#86efac"
        if "fail" in s or s == "error":
            return "#fca5a5"
        return "#fcd34d"

    def _status_chip_bg(self, state: str) -> str:
        s = (state or "").lower()
        if s in {"idle"}:
            return "#2b3442"
        if s in {"starting", "running", "continue_running", "logged_in", "navigated"}:
            return "#1e3a5f"
        if s in {"continue_done", "active_alarm_done", "download_upload_done", "south_comm_done", "calibration_done"}:
            return "#14532d"
        if "fail" in s or s == "error":
            return "#7f1d1d"
        return "#422006"


    def _apply_failure_ui(self):
        try:
            self.status_chip.config(fg=COLORS["text"], bg="#7f1d1d")
            self.status_var.set("Error")
            self.activity_dot.config(fg=COLORS["danger"])
            self.error_hint.config(text="FAILED", fg="#fecaca", bg=COLORS["panel"])
        except Exception:
            pass
        self._style_button(self.start_btn, True, COLORS["success"])
        self._style_button(self.continue_btn, False, COLORS["accent"])
        self._style_button(self.end_btn, False, COLORS["danger"])

    def _refresh_buttons(self):
        running = self._worker is not None and self._worker.is_alive()
        if self._state == "idle" and not running:
            self._style_button(self.start_btn, True, COLORS["success"])
            self._style_button(self.continue_btn, False, COLORS["accent"])
            self._style_button(self.end_btn, False, COLORS["danger"])
        elif (
            self._state
            in {
                "starting",
                "running",
                "continue_running",
                "logged_in",
                "navigated",
                "download_upload_done",
                "south_comm_done",
                "calibration_done",
                "active_alarm_done",
                "continue_done",
            }
            or running
        ):
            self._style_button(self.start_btn, False, COLORS["success"])
            can_continue = self._state == "active_alarm_done" and not running and bool(self.runner.page)
            # Continue is only enabled after the main flow reaches active_alarm_done.
            self._style_button(self.continue_btn, can_continue, COLORS["accent"])
            self._style_button(self.end_btn, True, COLORS["danger"])
        else:
            self._style_button(self.start_btn, True, COLORS["success"])
            self._style_button(self.continue_btn, False, COLORS["accent"])
            self._style_button(self.end_btn, False, COLORS["danger"])

    def _set_state(self, value: str):
        def _apply():
            self._state = value
            display = value.replace("_", " ").title()
            self.status_var.set(display)
            try:
                color = self._status_color(value)
                self.status_chip.config(
                    fg=color,
                    bg=self._status_chip_bg(value),
                    highlightbackground=color,
                    highlightcolor=color,
                    bd=1,
                )
                self.activity_dot.config(
                    fg=color if value.lower() not in {"idle"} else COLORS["text_dim"]
                )
                if value.lower() in {"idle"}:
                    self.error_hint.config(text="", fg="#bfdbfe", bg=COLORS["panel"])
                elif "fail" in value.lower() or value.lower() == "error":
                    self.error_hint.config(text="FAILED", fg="#fecaca", bg=COLORS["panel"])
                elif value.lower() in {"continue_done", "active_alarm_done", "download_upload_done", "south_comm_done", "calibration_done"}:
                    self.error_hint.config(text="OK", fg="#bbf7d0", bg=COLORS["panel"])
                elif value.lower() in {"starting", "running", "continue_running", "logged_in", "navigated"}:
                    self.error_hint.config(text="RUN", fg="#bfdbfe", bg=COLORS["panel"])
                else:
                    self.error_hint.config(text="WAIT", fg="#fcd34d", bg=COLORS["panel"])
            except Exception:
                pass
            self._refresh_buttons()

        try:
            self.after(0, _apply)
        except Exception:
            _apply()

    def _on_state_change(self, value: str):
        self._set_state(value)

    def _append_log_line(self, level: str, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        tag = level if level in {"info", "warning", "error"} else "info"
        if "success" in msg.lower() or "completed successfully" in msg.lower():
            tag = "success"
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{ts}] ", "time")
        self.log_text.insert("end", f"[{level.upper()}] {msg}\n", tag)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        self.log_meta_var.set(f"{ts} · {level.upper()}")

    def _drain_logs(self):
        try:
            while True:
                level, msg = self.log_queue.get_nowait()
                self._append_log_line(level, msg)
        except queue.Empty:
            pass
        self.after(100, self._drain_logs)

    def _start_worker(self, target):
        if self._worker and self._worker.is_alive():
            return
        self._worker = threading.Thread(target=target, daemon=True)
        self._worker.start()
        self._refresh_buttons()

    def _start_flow(self):
        ok = False
        try:
            self._set_state("starting")
            ui_cfg = self.config_data.get("ui", {})
            try:
                self.after(0, lambda: self.attributes("-alpha", float(ui_cfg.get("start_alpha", 0.60))))
                self.after(0, lambda: self.attributes("-topmost", True))
            except Exception:
                pass
            self.runner.start_browser()
            self.runner.open_home_and_login()
            self.runner.run_main_flow(include_south_communication=True)
            self.log_handler.info("Automation completed successfully")
            ok = True
            self._set_state("active_alarm_done")
        except Exception as e:
            self.log_handler.error("Automation failed: %s", str(e))
            try:
                self.runner.stop()
            except Exception:
                pass
            self.log_handler.error("Start failed, session cleaned up. Please click START again.")
        finally:
            self._worker = None
            if not ok:
                # Failed start: always return to idle so user can click Start again.
                self._set_state("idle")
                self._apply_failure_ui()
                try:
                    ui_cfg = self.config_data.get("ui", {})
                    self.after(
                        0,
                        lambda: self.attributes("-alpha", float(ui_cfg.get("idle_alpha", 0.75))),
                    )
                except Exception:
                    pass
            try:
                self.after(0, self._refresh_buttons)
            except Exception:
                self._refresh_buttons()

    def _continue_flow(self):
        ok = False
        try:
            if not self.runner.page:
                raise RuntimeError("No active browser session. Click Start first.")
            self.runner.run_continue_flow()
            ok = True
            self._set_state("continue_done")
        except Exception as e:
            self.log_handler.error("Continue failed: %s", str(e))
            try:
                self.runner.stop()
            except Exception:
                pass
            self.log_handler.error("Continue failed, session cleaned up. Please click START again.")
            self._set_state("idle")
            self._apply_failure_ui()
            try:
                ui_cfg = self.config_data.get("ui", {})
                self.after(0, lambda: self.attributes("-alpha", float(ui_cfg.get("idle_alpha", 0.75))))
            except Exception:
                pass
        finally:
            self._worker = None
            if not ok and self._state != "idle":
                self._set_state("idle")
            try:
                self.after(0, self._refresh_buttons)
            except Exception:
                self._refresh_buttons()

    def on_start(self):
        self._start_worker(self._start_flow)

    def on_continue(self):
        self._start_worker(self._continue_flow)

    def on_end(self):
        self.log_handler.info("End requested — closing browser window only (GUI stays open)")
        try:
            self.runner.stop()
        finally:
            self._worker = None
            try:
                ui_cfg = self.config_data.get("ui", {})
                self.after(0, lambda: self.attributes("-alpha", float(ui_cfg.get("idle_alpha", 0.75))))
            except Exception:
                pass
            self._set_state("idle")
            self._refresh_buttons()
            self.log_handler.info("Browser session closed. GUI remains open — click START for a new run.")


if __name__ == "__main__":
    App().mainloop()
