from __future__ import annotations

from playwright.sync_api import Page


def search_record(page: Page, keyword: str, config: dict, logger) -> int:
    search_cfg = config["search"]
    rows = page.locator(search_cfg["result_row_selector"])
    count = rows.count()
    logger.info("Current visible rows=%s for keyword=%s", count, keyword)
    return count
