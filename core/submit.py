from __future__ import annotations

from playwright.sync_api import Page, expect


def submit_upload(page: Page, logger) -> None:
    candidates = ["Upload", "Submit", "OK", "Apply", "Save"]

    for text in candidates:
        locator = page.get_by_text(text, exact=True)
        count = locator.count()
        if count == 0:
            continue

        for index in range(count):
            item = locator.nth(index)
            try:
                if item.is_visible():
                    item.click()
                    logger.info("Clicked submit button: %s", text)
                    return
            except Exception:
                continue

    raise ValueError("No visible submit button found after upload")
