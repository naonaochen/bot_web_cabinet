from __future__ import annotations

from pathlib import Path

from core.apply import apply_file
from core.auth import login
from core.browser import create_browser
from core.logger import get_logger
from core.navigation import navigate_to_target
from core.screenshot import save_screenshot
from core.utils import ensure_dir, load_config, now_str, safe_filename
from core.verify_apply import verify_apply_result


def run_task(target_file_name: str | None = None) -> None:
    config = load_config()
    logger = get_logger(__name__, config["files"]["log_dir"])

    ensure_dir(config["files"]["screenshot_dir"])
    ensure_dir(config["files"]["trace_dir"])

    target = target_file_name or config["apply"]["target_file_name"]

    playwright = browser = context = page = None
    trace_saved = False

    try:
        playwright, browser, context, page = create_browser(config)
        login(page, config, logger)
        navigate_to_target(page, config, logger)

        before_path = save_screenshot(page, config["files"]["screenshot_dir"], "before_apply")
        logger.info("Before apply screenshot saved: %s", before_path)

        apply_file(page, target, config, logger)

        page.wait_for_timeout(2000)
        after_path = save_screenshot(page, config["files"]["screenshot_dir"], "after_apply")
        logger.info("After apply screenshot saved: %s", after_path)

        if not verify_apply_result(page, target, logger):
            raise RuntimeError(f"Apply verification failed for {target}")

        logger.info("Apply flow completed for file: %s", target)
    finally:
        if context and not trace_saved:
            try:
                trace_file = Path(config["files"]["trace_dir"]) / f"trace_{safe_filename(now_str())}.zip"
                context.tracing.stop(path=str(trace_file))
                trace_saved = True
            except Exception:
                pass
        if browser:
            browser.close()
        if playwright:
            playwright.stop()
