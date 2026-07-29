from __future__ import annotations

from pathlib import Path

from core.auth import login
from core.browser import create_browser
from core.logger import get_logger
from core.navigation import navigate_to_setting_south_communication
from core.screenshot import save_screenshot
from core.south_communication import ensure_only_device_type_row, set_south_communication
from core.utils import ensure_dir, load_config, now_str, safe_filename
from core.verify_settings import verify_only_device_type, verify_south_communication_page


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
        navigate_to_setting_south_communication(page, config, logger)

        if not verify_south_communication_page(page, logger):
            raise RuntimeError("South Communication page verification failed")

        before_path = save_screenshot(page, config["files"]["screenshot_dir"], "setting_south_communication_before")
        logger.info("South Communication before screenshot saved: %s", before_path)

        set_south_communication(page, config, logger)
        page.wait_for_timeout(1000)
        ensure_only_device_type_row(page, config, logger)

        after_path = save_screenshot(page, config["files"]["screenshot_dir"], "setting_south_communication_after")
        logger.info("South Communication after screenshot saved: %s", after_path)

        target_device = config["south_communication"]["target_row_device_type"]
        if not verify_only_device_type(page, target_device, logger):
            raise RuntimeError(f"South Communication verification failed for {target_device}")

        logger.info("South Communication flow completed")
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
        if browser:
            browser.close()
        if playwright:
            playwright.stop()
