from __future__ import annotations

from playwright.sync_api import Page


def verify_calibration_page(page: Page, logger) -> bool:
    body_text = page.locator("body").inner_text()
    if "Maintenance->Calibration" in body_text or "Calibration" in body_text:
        logger.info("Calibration page verified")
        return True

    logger.warning("Calibration page verification failed")
    return False
