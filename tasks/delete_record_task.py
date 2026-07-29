from __future__ import annotations

from pathlib import Path

from core.auth import login
from core.browser import create_browser
from core.delete import delete_record
from core.logger import get_logger
from core.navigation import navigate_to_target
from core.screenshot import save_screenshot
from core.utils import ensure_dir, load_config, now_str, safe_filename
from core.verify import verify_deleted


def _save_trace(context, trace_dir: str) -> str:
    trace_file = Path(trace_dir) / f"trace_{safe_filename(now_str())}.zip"
    context.tracing.stop(path=str(trace_file))
    return str(trace_file)


def run_task(*target_file_names: str) -> None:
    config = load_config()
    logger = get_logger(__name__, config["files"]["log_dir"])

    ensure_dir(config["files"]["screenshot_dir"])
    ensure_dir(config["files"]["trace_dir"])

    targets = list(target_file_names) if target_file_names else config["delete"].get("deleted_files", [
        "default.csv",
        "VF3-Power core test-V1.csv",
    ])

    playwright = browser = context = page = None
    trace_saved = False

    try:
        playwright, browser, context, page = create_browser(config)
        login(page, config, logger)
        navigate_to_target(page, config, logger)

        before_path = save_screenshot(page, config["files"]["screenshot_dir"], "before_delete")
        logger.info("Before delete screenshot saved: %s", before_path)

        for target_file_name in targets:
            delete_record(page, target_file_name, config, logger)
            page.wait_for_timeout(1000)
            if not verify_deleted(page, target_file_name, config, logger):
                raise RuntimeError(f"Delete verification failed for {target_file_name}")

        after_path = save_screenshot(page, config["files"]["screenshot_dir"], "after_delete")
        logger.info("After delete screenshot saved: %s", after_path)

        logger.info("Delete flow completed for files: %s", ", ".join(targets))

    except Exception as e:
        if page:
            error_path = save_screenshot(
                page,
                config["files"]["screenshot_dir"],
                f"error_state_{now_str()}"
            )
            logger.error("Error screenshot saved: %s", error_path)

        if context and not trace_saved:
            trace_file = _save_trace(context, config["files"]["trace_dir"])
            trace_saved = True
            logger.error("Trace saved: %s", trace_file)

        logger.exception("Task failed: %s", e)
        raise

    finally:
        if context and not trace_saved:
            try:
                trace_file = _save_trace(context, config["files"]["trace_dir"])
                logger.info("Trace saved: %s", trace_file)
            except Exception:
                pass
        if browser:
            browser.close()
        if playwright:
            playwright.stop()
