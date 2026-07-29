from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from core.apply import apply_file
from core.auth import login
from core.browser import create_browser
from core.calibration import reset_calibration_parameters
from core.delete import keep_only_uploaded_files
from core.navigation import _click_menu_path, navigate_to_setting_south_communication, navigate_to_target
from core.screenshot import save_screenshot
from core.south_communication import ensure_only_device_type_row, set_south_communication
from core.submit import submit_upload
from core.toast import collect_visible_toast_texts, dismiss_toasts, latest_new_toast
from core.upload import upload_file
from core.verify_apply import verify_apply_result
from core.verify_calibration import verify_calibration_page
from core.verify_settings import (
    verify_only_device_type,
    verify_south_communication_page,
    verify_south_communication_saved,
)
from core.verify_upload import verify_upload_result


class FlowRunner:
    """
    Session-aware automation controller for GUI Start / Continue / End.

    Start: login + main production path, keep browser open.
    Continue: reuse current page/session for continue-stage actions.
    End: close browser/context and reset state.
    """

    def __init__(self, config: dict, log, on_state_change: Callable[[str], None] | None = None):
        self.config = config
        self.log = log
        self.on_state_change = on_state_change or (lambda _s: None)

        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

        self.stop_event = threading.Event()
        self._cleanup_lock = threading.Lock()
        self._cleanup_done = False
        self.state = "idle"

    def _set_state(self, state: str) -> None:
        self.state = state
        try:
            self.on_state_change(state)
        except Exception:
            pass

    def start_browser(self) -> None:
        self._cleanup_done = False
        self.stop_event.clear()
        self._set_state("starting")
        self.playwright, self.browser, self.context, self.page = create_browser(self.config)
        self.log.info("Browser started")

    def open_home_and_login(self) -> None:
        if not self.page:
            raise RuntimeError("No active page. Call start_browser() first.")
        self.log.info("Opening login page...")
        login(self.page, self.config, self.log)
        self.log.info("Login successful")
        self._set_state("logged_in")

    def run_main_flow(self, *, include_south_communication: bool = True) -> None:
        """Full Start path. Leaves browser open for Continue/End."""
        if not self.page:
            raise RuntimeError("No active page. Call start_browser() first.")
        page = self.page
        config = self.config
        log = self.log
        screenshot_dir = config["files"]["screenshot_dir"]
        ui = config.get("ui", {})

        log.info("Waiting for page to stabilize after login...")
        page.wait_for_timeout(int(ui.get("loading_wait_ms", 500)) + 2500)

        log.info("Navigating to target page...")
        navigate_to_target(page, config, log)
        self._set_state("navigated")

        upload_files = list(config.get("flow", {}).get("upload_files", []))
        apply_target = (
            config.get("flow", {}).get("apply_target_file")
            or config.get("apply", {}).get("target_file_name")
        )
        if not upload_files:
            raise RuntimeError("flow.upload_files is empty")
        if not apply_target:
            raise RuntimeError("No apply target configured")

        save_screenshot(page, screenshot_dir, "01_before_upload")
        target_upload_names = [Path(f).name for f in upload_files]
        uploaded_names: list[str] = []
        missing: list[str] = []

        for name in target_upload_names:
            if verify_upload_result(page, name, log):
                log.info("File already exists, skip upload: %s", name)
                uploaded_names.append(name)
            else:
                missing.append(name)

        if missing:
            for i, name in enumerate(missing, 1):
                if self.stop_event.is_set():
                    raise RuntimeError("Stopped by user")
                path = next((f for f in upload_files if Path(f).name == name), None)
                if not path:
                    continue
                log.info("[%d/%d] Uploading %s", i, len(missing), name)
                resolved = upload_file(page, path, config, log)
                uploaded_names.append(Path(resolved).name)
                page.wait_for_timeout(int(ui.get("upload_gap_ms", 2000)))
            submit_upload(page, log)
            page.wait_for_timeout(int(ui.get("loading_wait_ms", 500)) + 4500)
        else:
            log.info("All target files already present; skip upload/submit")

        if not uploaded_names:
            uploaded_names = target_upload_names

        for name in uploaded_names:
            if not verify_upload_result(page, name, log):
                raise RuntimeError(f"Upload verification failed for {name}")
        self._set_state("download_upload_done")
        save_screenshot(page, screenshot_dir, "02_after_upload")

        log.info("Applying target file: %s", apply_target)
        apply_file(page, apply_target, config, log)
        page.wait_for_timeout(int(config.get("timeouts", {}).get("apply_wait_ms", 3000)))
        if not verify_apply_result(page, apply_target, log):
            log.warning("Apply verification soft-failed; continuing")
        save_screenshot(page, screenshot_dir, "03_after_apply")

        save_screenshot(page, screenshot_dir, "04_before_delete")
        keep_only_uploaded_files(page, config, log, [Path(f).name for f in upload_files])
        save_screenshot(page, screenshot_dir, "05_after_delete")

        if include_south_communication:
            self._run_south_communication()
        else:
            log.info("South Communication skipped")

        self._run_calibration()
        self._run_active_alarm()
        self._set_state("active_alarm_done")
        log.info("Main flow finished; session kept open for Continue/End")

    def run_continue_flow(self) -> None:
        """Reuse current session for continue-stage Download/Upload + Other Control."""
        if not self.page:
            raise RuntimeError("No active browser session. Click Start first.")
        if self.state == "idle":
            raise RuntimeError("Session is idle. Click Start first.")

        page = self.page
        config = self.config
        log = self.log
        screenshot_dir = config["files"]["screenshot_dir"]
        ui = config.get("ui", {})
        continue_cfg = config.get("flow", {}).get("continue", {})

        self._set_state("continue_running")
        log.info("Continue: Download/Upload stage")

        menu_path = continue_cfg.get(
            "download_upload_menu_path",
            config.get("navigation", {}).get("menus", ["Maintenance", "Download/Upload"]),
        )
        _click_menu_path(page, menu_path, log)
        page.wait_for_timeout(int(ui.get("continue_stage_nav_wait_ms", 1500)))

        target_file = continue_cfg.get("target_file") or continue_cfg.get("keep_only_file")
        if not target_file:
            raise RuntimeError("flow.continue.target_file is not configured")

        apply_cfg = dict(config.get("apply", {}))
        apply_cfg["apply_button_text"] = continue_cfg.get(
            "apply_button_text", apply_cfg.get("apply_button_text", "Apply")
        )
        apply_cfg["success_toast_text"] = continue_cfg.get(
            "success_toast_text", apply_cfg.get("success_toast_text", "Apply Para Success")
        )
        apply_cfg["started_toast_text"] = apply_cfg.get("started_toast_text", "Start Application")
        temp_config = dict(config)
        temp_config["apply"] = apply_cfg

        dismiss_toasts(page)
        baseline = collect_visible_toast_texts(page)
        apply_file(page, target_file, temp_config, log)
        page.wait_for_timeout(int(config.get("timeouts", {}).get("apply_wait_ms", 3000)))
        matched = latest_new_toast(page, baseline, apply_cfg["success_toast_text"])
        if matched:
            log.info("Continue Apply toast: %s", matched)
        save_screenshot(page, screenshot_dir, "continue_after_apply")

        keep_file = continue_cfg.get("keep_only_file") or target_file
        keep_only_uploaded_files(page, config, log, [Path(keep_file).name])
        save_screenshot(page, screenshot_dir, "continue_after_delete")

        self._run_other_control()
        self._set_state("continue_done")
        log.info("Continue flow finished; session still open until End")

    def _run_south_communication(self) -> None:
        page = self.page
        config = self.config
        log = self.log
        screenshot_dir = config["files"]["screenshot_dir"]
        ui = config.get("ui", {})

        navigate_to_setting_south_communication(page, config, log)
        if not verify_south_communication_page(page, log):
            raise RuntimeError("South Communication page verification failed")
        save_screenshot(page, screenshot_dir, "05_before_south_communication")
        set_south_communication(page, config, log)
        page.wait_for_timeout(int(ui.get("south_comm_ready_wait_ms", 2000)))
        target_fields = config["south_communication"]["target_row_fields"]
        if not verify_south_communication_saved(page, target_fields, log):
            raise RuntimeError("South Communication save verification failed")
        ensure_only_device_type_row(page, config, log)
        if not verify_only_device_type(page, target_fields, log):
            raise RuntimeError("South Communication only-device-type verification failed")
        save_screenshot(page, screenshot_dir, "06_after_south_communication")
        self._set_state("south_comm_done")

    def _run_calibration(self) -> None:
        page = self.page
        config = self.config
        log = self.log
        path = config["navigation"].get("calibration_menu_path", ["Maintenance", "Calibration"])
        _click_menu_path(page, path, log)
        if not verify_calibration_page(page, log):
            raise RuntimeError("Calibration page verification failed")
        cal_cfg = config.get("calibration", {})
        names = cal_cfg.get("parameter_names") or [
            "DC Voltage",
            "Battery 1 Voltage",
            "Battery 2 Voltage",
        ]
        reset_calibration_parameters(
            page,
            names,
            log,
            reset_delay_ms=cal_cfg.get("reset_delay_ms", 5000),
            visible_progress_ms=cal_cfg.get("visible_progress_ms", 1000),
        )
        save_screenshot(page, config["files"]["screenshot_dir"], "07_after_calibration")
        self._set_state("calibration_done")

    def _run_active_alarm(self) -> None:
        page = self.page
        config = self.config
        log = self.log
        path = config["navigation"].get("active_alarm_menu_path", ["Active Alarm"])
        _click_menu_path(page, path, log)
        page.wait_for_timeout(int(config.get("ui", {}).get("active_alarm_nav_wait_ms", 1000)))
        save_screenshot(page, config["files"]["screenshot_dir"], "08_active_alarm")
        self._set_state("active_alarm_done")

    def _run_other_control(self) -> None:
        page = self.page
        config = self.config
        log = self.log
        ui = config.get("ui", {})
        oc = config.get("other_control", {})
        menu = config.get("navigation", {}).get(
            "other_control_menu_path",
            ["Maintenance", "Other Control"],
        )
        _click_menu_path(page, menu, log)
        page.wait_for_timeout(int(ui.get("active_alarm_nav_wait_ms", 1000)))

        yes_text = oc.get("yes_button_text", "YES")
        save_text = oc.get("save_button_text", "Save")
        row_selector = oc.get("row_selector", "table tbody tr")
        controls = oc.get("controls", [])

        for idx, control in enumerate(controls):
            if self.stop_event.is_set():
                raise RuntimeError("Stopped by user")
            name = control.get("name", "")
            if not name:
                continue
            success_message = control.get("success_message", "job success")
            timeout_ms = int(control.get("timeout_ms", 15000))
            if idx > 0:
                page.wait_for_timeout(int(ui.get("delete_confirm_wait_ms", 1000)))
            log.info("Other Control: %s", name)

            rows = page.locator(row_selector)
            found = False
            for i in range(rows.count()):
                row = rows.nth(i)
                try:
                    row_text = row.inner_text().strip()
                except Exception:
                    continue
                if name.lower() not in row_text.lower():
                    continue
                found = True
                yes_btn = row.get_by_text(yes_text, exact=True)
                if yes_btn.count() == 0:
                    raise RuntimeError(f"{yes_text} not found for {name}")
                if yes_btn.first.is_disabled():
                    log.warning("YES already disabled for %s", name)
                    break
                dismiss_toasts(page)
                baseline = collect_visible_toast_texts(page)
                yes_btn.first.click(force=True)
                page.wait_for_selector(f"text={save_text}", timeout=int(config.get("timeouts", {}).get("dialog_button_timeout_ms", 5000)))
                dialog = page.locator(
                    "div[role='dialog'], .el-dialog, .el-message-box, .modal, .ant-modal"
                ).filter(has_text=save_text)
                if dialog.count() == 0:
                    dialog = page.locator("div[role='dialog'], .el-dialog, .el-message-box, .modal, .ant-modal")
                if dialog.count() == 0:
                    raise RuntimeError(f"Dialog not found for {name}")
                d = dialog.first
                primary = d.locator(".el-dialog__footer button.el-button--primary")
                clicked = False
                if primary.count() > 0:
                    for pidx in range(primary.count()):
                        cand = primary.nth(pidx)
                        if cand.is_visible():
                            cand.click(force=True)
                            clicked = True
                            break
                if not clicked:
                    save_btn = d.get_by_role("button", name=save_text)
                    if save_btn.count() == 0:
                        save_btn = d.get_by_text(save_text, exact=True)
                    save_btn.first.click(force=True)
                page.wait_for_timeout(max(timeout_ms, 200))
                matched = latest_new_toast(page, baseline, success_message)
                if matched:
                    log.info("Other Control success toast for %s: %s", name, matched)
                else:
                    page.wait_for_selector(f"text={success_message}", timeout=timeout_ms)
                    log.info("Other Control success text for %s: %s", name, success_message)
                break
            if not found:
                raise RuntimeError(f"Control not found: {name}")

        save_screenshot(page, config["files"]["screenshot_dir"], "continue_after_other_control")

    def stop(self) -> None:
        """End session: stop flags, close browser, reset state."""
        self.stop_event.set()
        with self._cleanup_lock:
            if self._cleanup_done:
                self._set_state("idle")
                return
            self._cleanup_done = True
            try:
                if self.context:
                    try:
                        self.context.close()
                    except Exception:
                        pass
                if self.browser:
                    try:
                        self.browser.close()
                    except Exception:
                        pass
                if self.playwright:
                    try:
                        self.playwright.stop()
                    except Exception:
                        pass
            finally:
                self.page = None
                self.context = None
                self.browser = None
                self.playwright = None
                self._set_state("idle")
                self.log.info("Session closed")
