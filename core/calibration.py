from __future__ import annotations

from playwright.sync_api import Page, expect

from .utils import get_safe_row_text


def _find_row_by_parameter(page: Page, parameter_name: str):
    rows = page.locator("table tbody tr")
    for i in range(rows.count()):
        row = rows.nth(i)
        text = get_safe_row_text(row)
        if parameter_name == text or parameter_name in text:
            return row
    return None


def reset_calibration_parameters(
    page: Page,
    parameter_names: list[str],
    logger,
    reset_delay_ms: int = 5000,
    visible_progress_ms: int = 1000,
) -> None:
    rows = page.locator("table tbody tr")
    if rows.count() == 0:
        raise RuntimeError("No calibration rows found")

    for parameter_name in parameter_names:
        row = _find_row_by_parameter(page, parameter_name)
        if row is None:
            logger.info("Calibration row not found, skip reset: %s", parameter_name)
            continue

        reset_btn = row.get_by_text("Reset", exact=True)
        if reset_btn.count() == 0:
            logger.info("Reset button not found, skip: %s", parameter_name)
            continue

        try:
            expect(reset_btn.first).to_be_visible()
            logger.info("Clicking Reset for parameter: %s", parameter_name)
            reset_btn.first.click(force=True)
            logger.info("Reset action sent for parameter: %s", parameter_name)
            page.wait_for_timeout(visible_progress_ms)
            logger.info("Reset in progress for parameter: %s", parameter_name)
            page.wait_for_timeout(max(0, reset_delay_ms - visible_progress_ms))
            logger.info("Reset completed for parameter: %s", parameter_name)
        except Exception:
            logger.info("Failed to reset parameter: %s", parameter_name)
