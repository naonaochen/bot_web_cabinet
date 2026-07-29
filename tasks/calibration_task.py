from __future__ import annotations

from pathlib import Path

from core.auth import login
from core.browser import create_browser
from core.calibration import reset_calibration_parameters
from core.logger import get_logger
from core.navigation import _click_menu_path
from core.screenshot import save_screenshot
from core.utils import ensure_dir, load_config, now_str, safe_filename
from core.verify_calibration import verify_calibration_page


def run_task() -> None:
    config = load_config()
    logger = get_logger(__name__, config["files"]["log_dir"])

    ensure_dir(config["files"]["screenshot_dir"])
    ensure_dir(config["files"]["trace_dir"])

    playwright = browser = context = page = None
    trace_saved = False

    try:
        playwright, browser, context, page = create_browser(config)
        login(page, config, logger)

        path = config["navigation"].get("calibration_menu_path", ["Maintenance", "Calibration"])
        _click_menu_path(page, path, logger)

        if not verify_calibration_page(page, logger):
            raise RuntimeError("Calibration page verification failed")

        before_img = save_screenshot(page, config["files"]["screenshot_dir"], "calibration_before_reset")
        logger.info("Calibration before screenshot saved: %s", before_img)

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

        after_img = save_screenshot(page, config["files"]["screenshot_dir"], "calibration_after_reset")
        logger.info("Calibration after screenshot saved: %s", after_img)

        active_alarm_path = config["navigation"].get("active_alarm_menu_path", ["Active Alarm"])
        _click_menu_path(page, active_alarm_path, logger)
        logger.info("Navigated to Active Alarm")

    except Exception as e:
        if page:
            error_path = save_screenshot(page, config["files"]["screenshot_dir"], f"error_state_{now_str()}")
            logger.error("Error screenshot saved: %s", error_path)

        if context and not trace_saved:
            trace_file = Path(config["files"]["trace_dir"]) / f"trace_{safe_filename(now_str())}.zip"
            context.tracing.stop(path=str(trace_file))
            trace_saved = True
            logger.error("Trace saved: %s", trace_file)

        logger.exception("Task failed: %s", e)
        raise
    finally:
        if context and not trace_saved:
            try:
                trace_file = Path(config["files"]["trace_dir"]) / f"trace_{safe_filename(now_str())}.zip"
                context.tracing.stop(path=str(trace_file))
                logger.info("Trace saved: %s", trace_file)
            except Exception:
                pass
        if page:
            try:
                page.bring_to_front()
            except Exception:
                pass
