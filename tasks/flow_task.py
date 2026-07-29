from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from core.apply import apply_file
from core.auth import login
from core.browser import create_browser
from core.calibration import reset_calibration_parameters
from core.delete import delete_record
from core.logger import get_logger
from core.navigation import _click_menu_path, navigate_to_setting_south_communication, navigate_to_target
from core.screenshot import save_screenshot
from core.submit import submit_upload
from core.south_communication import ensure_only_device_type_row, set_south_communication
from core.upload import upload_file
from core.utils import check_url_reachable, ensure_dir, load_config, now_str, safe_filename
from core.verify import verify_deleted
from core.verify_apply import verify_apply_result
from core.verify_calibration import verify_calibration_page
from core.verify_settings import verify_only_device_type, verify_south_communication_page, verify_south_communication_saved
from core.verify_upload import verify_upload_result


def _save_trace(context, trace_dir: str) -> str:
    trace_file = Path(trace_dir) / f"trace_{safe_filename(now_str())}.zip"
    try:
        context.tracing.stop(path=str(trace_file))
    except Exception:
        return ""
    return str(trace_file)


def _utc_now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _resolve_list(cli_values: list[str] | None, cfg_values: list[str] | None) -> list[str]:
    if cli_values:
        return cli_values
    return cfg_values or []


def run_flow(
    *upload_file_paths: str,
    apply_target_file: str | None = None,
    delete_targets: tuple[str, ...] | None = None,
    config_path: str = "config/settings.yaml",
    report_path: str | None = None,
    include_south_communication: bool = True,
    precheck_network: bool = True,
    close_browser_at_end: bool = False,
    pause_at_end: bool = True,
) -> None:
    config = load_config(config_path)
    logger = get_logger(__name__, config["files"]["log_dir"])

    ensure_dir(config["files"]["screenshot_dir"])
    ensure_dir(config["files"]["trace_dir"])
    ensure_dir(Path(report_path).parent if report_path else Path(config["files"]["log_dir"]))

    app_url = config["app"]["url"]
    if precheck_network:
        reachable, reason = check_url_reachable(app_url)
        if not reachable:
            raise RuntimeError(f"Network precheck failed for {app_url}: {reason}")
        logger.info("Network precheck passed for %s (%s)", app_url, reason)

    cfg_upload_files = config.get("flow", {}).get("upload_files", [])
    cfg_apply_target = config.get("flow", {}).get("apply_target_file") or config.get("apply", {}).get("target_file_name")
    cfg_delete_targets = config.get("flow", {}).get("delete_targets") or config.get("delete", {}).get("deleted_files", [])

    upload_files = _resolve_list(list(upload_file_paths), cfg_upload_files)
    apply_target = apply_target_file or cfg_apply_target
    delete_list = list(delete_targets) if delete_targets else list(cfg_delete_targets)

    report: dict[str, Any] = {
        "started_at": _utc_now_iso(),
        "config_path": config_path,
        "upload_files": upload_files,
        "apply_target_file": apply_target,
        "delete_targets": delete_list,
        "include_south_communication": include_south_communication,
        "precheck_network": precheck_network,
        "steps": [],
        "status": "running",
    }

    playwright = browser = context = page = None
    trace_saved = False

    def add_step(name: str, status: str, detail: str = "") -> None:
        report["steps"].append(
            {
                "name": name,
                "status": status,
                "detail": detail,
                "timestamp": _utc_now_iso(),
            }
        )

    try:
        playwright, browser, context, page = create_browser(config)
        
        # Login (may require manual captcha input)
        logger.info("Starting login process...")
        login(page, config, logger)
        
        # After successful login, inform user that automation continues
        logger.info("=" * 60)
        logger.info("✓ Login successful! Automation continuing automatically...")
        logger.info("=" * 60)
        logger.info("")
        
        # Wait a bit for page to fully load after login
        logger.info("Waiting for page to stabilize after login...")
        page.wait_for_timeout(3000)
        
        logger.info("Navigating to target page...")
        navigate_to_target(page, config, logger)
        add_step("login_and_navigate", "passed")
        logger.info("✓ Navigation completed successfully")

        before_upload = save_screenshot(page, config["files"]["screenshot_dir"], "01_before_upload")
        logger.info("Before upload screenshot saved: %s", before_upload)

        uploaded_names: list[str] = []
        target_upload_names = [Path(f).name for f in upload_files]
        logger.info("=" * 60)
        logger.info("Starting file upload process...")
        logger.info("Total target files: %d", len(upload_files))
        logger.info("Target files: %s", ", ".join(target_upload_names))
        logger.info("=" * 60)
        
        existing_uploaded = []
        missing_uploads = []
        for target_file in target_upload_names:
            if verify_upload_result(page, target_file, logger):
                logger.info("✓ File already exists, skip upload: '%s'", target_file)
                uploaded_names.append(target_file)
                existing_uploaded.append(target_file)
            else:
                logger.info("File not found on page, will upload: '%s'", target_file)
                missing_uploads.append(target_file)

        if missing_uploads:
            logger.info("")
            logger.info("Uploading %d missing file(s)...", len(missing_uploads))
            for i, file_name in enumerate(missing_uploads, 1):
                file_path = next((f for f in upload_files if Path(f).name == file_name), None)
                if not file_path:
                    continue
                logger.info("")
                logger.info("[%d/%d] Uploading file...", i, len(missing_uploads))
                resolved = upload_file(page, file_path, config, logger)
                uploaded_name = Path(resolved).name
                uploaded_names.append(uploaded_name)
                logger.info("✓ File %d/%d uploaded successfully: '%s'", i, len(missing_uploads), uploaded_name)
                if i < len(missing_uploads):
                    logger.info("Waiting for page to update before next upload...")
                    page.wait_for_timeout(2000)

            logger.info("")
            logger.info("=" * 60)
            logger.info("Uploaded missing files. Submitting...")
            logger.info("Uploaded files: %s", ", ".join(uploaded_names))
            logger.info("=" * 60)

            submit_upload(page, logger)
            page.wait_for_timeout(5000)
            after_upload = save_screenshot(page, config["files"]["screenshot_dir"], "02_after_upload")
            logger.info("After upload screenshot saved: %s", after_upload)
        else:
            logger.info("")
            logger.info("=" * 60)
            logger.info("All target files already exist; skipping upload and submit.")
            logger.info("Keeping existing files: %s", ", ".join(existing_uploaded))
            logger.info("=" * 60)
            after_upload = save_screenshot(page, config["files"]["screenshot_dir"], "02_after_upload_skipped")
            logger.info("After upload skipped screenshot saved: %s", after_upload)

        if not uploaded_names:
            uploaded_names = target_upload_names

        logger.info("")
        logger.info("=" * 60)
        logger.info("Verifying uploaded files...")
        logger.info("=" * 60)

        logger.info("")
        logger.info("=" * 60)
        logger.info("Verifying uploaded files...")
        logger.info("=" * 60)
        
        for i, file_name in enumerate(uploaded_names, 1):
            logger.info("")
            logger.info("[%d/%d] Verifying file: '%s'", i, len(uploaded_names), file_name)
            if not verify_upload_result(page, file_name, logger):
                logger.error("✗ Verification FAILED for file %d/%d: '%s'", i, len(uploaded_names), file_name)
                raise RuntimeError(f"Upload verification failed for {file_name}")
            logger.info("✓ File %d/%d verified successfully: '%s'", i, len(uploaded_names), file_name)
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("✓ All %d files verified successfully!", len(uploaded_names))
        logger.info("=" * 60)
        add_step("upload", "passed", ", ".join(uploaded_names))

        # STEP 1: Click Apply button for the selected target before deletion
        logger.info("")
        logger.info("=" * 60)
        logger.info("STEP 1: Clicking Apply button for: '%s'", apply_target)
        logger.info("This allows user to see the Apply operation completed BEFORE deletions")
        logger.info("=" * 60)
        
        try:
            if not apply_target:
                raise ValueError("No apply target file configured or provided via CLI")
            apply_file(page, apply_target, config, logger)
            page.wait_for_timeout(5000)  # Wait for processing
            if verify_apply_result(page, apply_target, logger):
                logger.info("✓ Apply button clicked and verified successfully for: '%s'", apply_target)
                add_step("apply_final", "passed", f"Applied {apply_target}")
            else:
                logger.warning(" Apply verification failed but continuing...")
                add_step("apply_final", "warning", f"Apply verification failed for {apply_target}")
        except Exception as e:
            logger.warning("Failed to click Apply for '%s': %s", apply_target, str(e))
            logger.warning("Continuing with automation...")
            add_step("apply_final", "warning", f"Apply failed for {apply_target}")
        
        # Take screenshot after Apply
        after_apply_screenshot = save_screenshot(page, config["files"]["screenshot_dir"], "03_after_apply")
        logger.info("Screenshot after Apply saved: %s", after_apply_screenshot)

        # STEP 2: Delete all other files except uploaded ones
        before_delete = save_screenshot(page, config["files"]["screenshot_dir"], "04_before_delete")
        logger.info("Before delete screenshot saved: %s", before_delete)

        # Use new function to keep only uploaded files and delete all others
        from core.delete import keep_only_uploaded_files
        
        # Get list of uploaded filenames (extract just filename from full path)
        uploaded_filenames = [Path(f).name for f in upload_files]
        logger.info("")
        logger.info("STEP 2: Uploaded files to keep: %s", uploaded_filenames)
        logger.info("Deleting all other files...")
        
        # Call the new cleanup function
        deleted_files = keep_only_uploaded_files(page, config, logger, uploaded_filenames)
        
        add_step("delete", "passed", f"Deleted {len(deleted_files)} file(s)")

        after_delete = save_screenshot(page, config["files"]["screenshot_dir"], "05_after_delete")
        logger.info("After delete screenshot saved: %s", after_delete)

        if include_south_communication:
            navigate_to_setting_south_communication(page, config, logger)
            if not verify_south_communication_page(page, logger):
                raise RuntimeError("South Communication page verification failed")
            before_sc = save_screenshot(page, config["files"]["screenshot_dir"], "05_before_south_communication")
            logger.info("South Communication before screenshot saved: %s", before_sc)

            set_south_communication(page, config, logger)
            page.wait_for_timeout(2000)
            target_fields = config["south_communication"]["target_row_fields"]
            if not verify_south_communication_saved(page, target_fields, logger):
                raise RuntimeError(f"South Communication save verification failed for {target_fields}")

            ensure_only_device_type_row(page, config, logger)

            after_sc = save_screenshot(page, config["files"]["screenshot_dir"], "06_after_south_communication")
            logger.info("South Communication after screenshot saved: %s", after_sc)

            if not verify_only_device_type(page, target_fields, logger):
                raise RuntimeError(f"South Communication verification failed for {target_fields}")
            add_step("south_communication", "passed", config["south_communication"]["device_type_value"])
        else:
            add_step("south_communication", "skipped")

        path = config["navigation"].get("calibration_menu_path", ["Maintenance", "Calibration"])
        _click_menu_path(page, path, logger)
        if not verify_calibration_page(page, logger):
            raise RuntimeError("Calibration page verification failed")
        calibration_cfg = config.get("calibration", {})
        reset_delay_ms = calibration_cfg.get("reset_delay_ms", 5000)
        visible_progress_ms = calibration_cfg.get("visible_progress_ms", 1000)
        reset_calibration_parameters(
            page,
            ["DC Voltage", "Battery 1 Voltage", "Battery 2 Voltage"],
            logger,
            reset_delay_ms=reset_delay_ms,
            visible_progress_ms=visible_progress_ms,
        )
        calibration_img = save_screenshot(page, config["files"]["screenshot_dir"], "07_after_calibration")
        logger.info("Calibration screenshot saved: %s", calibration_img)
        add_step("calibration", "passed", " > ".join(path))

        active_alarm_path = config["navigation"].get("active_alarm_menu_path", ["Active Alarm"])
        _click_menu_path(page, active_alarm_path, logger)
        add_step("active_alarm", "passed", " > ".join(active_alarm_path))

        report["status"] = "passed"
        report["finished_at"] = _utc_now_iso()
        report["result"] = {
            "uploaded_files": uploaded_names,
            "applied_file": apply_target,
            "deleted_files": deleted_files,
            "south_communication_device_type": config["south_communication"]["device_type_value"] if include_south_communication else None,
            "screenshots": {
                "before_upload": before_upload,
                "after_upload": after_upload,
                "before_delete": before_delete,
                "after_delete": after_delete,
                "calibration": calibration_img,
            },
        }
        logger.info("Flow completed. uploaded=%s, applied=%s, deleted=%s", ", ".join(uploaded_names), apply_target, ", ".join(deleted_files))

    except Exception as e:
        report["status"] = "failed"
        report["finished_at"] = _utc_now_iso()
        report["error"] = str(e)
        add_step("flow", "failed", str(e))

        if page:
            try:
                error_path = save_screenshot(page, config["files"]["screenshot_dir"], f"error_state_{now_str()}")
                if error_path:
                    report.setdefault("screenshots", {})["error_state"] = error_path
                    logger.error("Error screenshot saved: %s", error_path)
            except Exception:
                pass

        if context and not trace_saved:
            try:
                trace_file = _save_trace(context, config["files"]["trace_dir"])
                if trace_file:
                    trace_saved = True
                    report["trace_file"] = trace_file
                    logger.error("Trace saved: %s", trace_file)
            except Exception:
                pass

        logger.exception("Task failed: %s", e)
        raise

    finally:
        if context and not trace_saved:
            try:
                trace_file = _save_trace(context, config["files"]["trace_dir"])
                if trace_file:
                    trace_saved = True
                    report["trace_file"] = trace_file
                    logger.info("Trace saved: %s", trace_file)
            except Exception:
                pass
        if pause_at_end and page:
            try:
                page.bring_to_front()
                page.wait_for_timeout(5000)
                logger.info("Flow finished. Browser left open for review.")
            except Exception:
                logger.info("Flow finished. Browser left open.")
        elif browser and close_browser_at_end:
            browser.close()
        if playwright and close_browser_at_end:
            playwright.stop()

        if report_path:
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
