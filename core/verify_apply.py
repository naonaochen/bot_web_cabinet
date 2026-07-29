from __future__ import annotations

from playwright.sync_api import Page

from .toast import latest_new_toast


def verify_apply_result(page: Page, target_file_name: str, logger) -> bool:
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)

    # Lightweight verification: if any success-style toast is currently visible,
    # treat Apply as successful for the caller.
    if latest_new_toast(page, None, "Apply Para Success") or latest_new_toast(page, None, "Start Application"):
        logger.info("Apply success toast detected for %s", target_file_name)
        return True

    logger.warning("Apply verification failed for %s (no success toast)", target_file_name)
    return False
