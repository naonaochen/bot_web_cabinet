from __future__ import annotations

from pathlib import Path

from core.auth import login
from core.browser import create_browser
from core.logger import get_logger
from core.navigation import navigate_to_target
from core.screenshot import save_screenshot
from core.submit import submit_upload
from core.upload import upload_file
from core.utils import ensure_dir, load_config, now_str, safe_filename
from core.verify_upload import verify_upload_result


def run_task(*file_paths: str) -> None:
    config = load_config()
    logger = get_logger(__name__, config["files"]["log_dir"])

    ensure_dir(config["files"]["screenshot_dir"])
    ensure_dir(config["files"]["trace_dir"])

    playwright = browser = context = page = None
    trace_saved = False

    try:
        playwright, browser, context, page = create_browser(config)
        login(page, config, logger)
        navigate_to_target(page, config, logger)

        before_path = save_screenshot(page, config["files"]["screenshot_dir"], "before_upload")
        logger.info("Before upload screenshot saved: %s", before_path)

        resolved_files = []
        for file_path in file_paths:
            resolved_file = upload_file(page, file_path, config, logger)
            resolved_files.append(Path(resolved_file).name)

        submit_upload(page, logger)

        after_path = save_screenshot(page, config["files"]["screenshot_dir"], "after_upload")
        logger.info("After upload screenshot saved: %s", after_path)

        for file_name in resolved_files:
            if not verify_upload_result(page, file_name, logger):
                raise RuntimeError(f"Upload verification failed for {file_name}")

        logger.info("Upload flow completed for files: %s", ", ".join(resolved_files))
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
