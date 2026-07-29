from __future__ import annotations

from playwright.sync_api import Page


def verify_deleted(page: Page, target_file_name: str, config: dict, logger) -> bool:
    delete_cfg = config["delete"]
    success_text = delete_cfg.get("success_message_text", "")

    if success_text:
        page.wait_for_timeout(500)
        body_text = page.locator("body").inner_text()
        if success_text not in body_text:
            logger.warning("Success text not found after delete: %s", success_text)

    rows = page.locator("table tbody tr")
    count = rows.count()

    for i in range(count):
        row_text = rows.nth(i).inner_text()
        if target_file_name in row_text:
            logger.error("Verification failed: file still exists=%s", target_file_name)
            return False

    logger.info("Verification passed: file removed=%s", target_file_name)
    return True
