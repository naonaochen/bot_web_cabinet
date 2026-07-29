from __future__ import annotations

from playwright.sync_api import Page


def verify_south_communication_page(page: Page, logger) -> bool:
    body_text = page.locator("body").inner_text()
    if "Setting->South Communication" in body_text or "South Communication" in body_text:
        logger.info("South Communication page verified")
        return True

    logger.warning("South Communication page verification failed")
    return False


def verify_only_device_type(page: Page, target_row_fields: list[str], logger) -> bool:
    rows = page.locator("table tbody tr")
    count = rows.count()
    if count == 0:
        logger.warning("South Communication table is empty")
        return False

    for i in range(count):
        row_text = rows.nth(i).inner_text().strip()
        if all(field in row_text for field in target_row_fields):
            logger.info("South Communication table verification passed for exact row: %s", row_text)
            return True

    logger.warning("South Communication exact target row not found")
    return False


def verify_south_communication_saved(page: Page, target_row_fields: list[str], logger) -> bool:
    rows = page.locator("table tbody tr")
    for i in range(rows.count()):
        row_text = rows.nth(i).inner_text().strip()
        if all(field in row_text for field in target_row_fields):
            logger.info("South Communication save verified by exact row: %s", row_text)
            return True

    logger.warning("South Communication save verification failed for exact row")
    return False
