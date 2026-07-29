from __future__ import annotations

from playwright.sync_api import Page


def _normalize_text(text: str) -> str:
    return " ".join((text or "").split())


def normalize_filename(value: str) -> str:
    return (value or "").replace("\\", "/").rsplit("/", 1)[-1].strip()


def verify_upload_result(page: Page, file_name: str, logger) -> bool:
    clean_file_name = normalize_filename(file_name)
    row_selector = "table tbody tr"

    page.wait_for_timeout(1000)
    try:
        page.wait_for_load_state("networkidle", timeout=3000)
    except Exception:
        pass

    max_checks = 20
    interval_ms = 500
    found_files: list[str] = []

    for attempt in range(1, max_checks + 1):
        rows = page.locator(row_selector)
        row_count = rows.count()

        logger.info("Checking for file '%s' in table with %d rows (attempt %d/%d)", file_name, row_count, attempt, max_checks)
        found_files = []

        for i in range(row_count):
            row_text = rows.nth(i).inner_text().strip()
            found_files.append(row_text)
            logger.info("  Row %d: '%s'", i + 1, row_text)

        for i in range(row_count):
            row_text = rows.nth(i).inner_text().strip()
            cleaned_row = _normalize_text(row_text)
            row_file = normalize_filename(cleaned_row)
            if clean_file_name == row_file or clean_file_name in cleaned_row:
                logger.info("✓ Upload verification passed: EXACT match found -> '%s' in '%s'", file_name, cleaned_row)
                return True

        for i in range(row_count):
            row_text = rows.nth(i).inner_text().strip()
            row_file = normalize_filename(row_text)
            if clean_file_name in row_file or clean_file_name in row_text:
                logger.info("✓ Upload verification passed: PARTIAL match found -> '%s' in '%s'", file_name, row_text)
                return True

        body_text = page.locator("body").inner_text()
        if file_name in body_text:
            logger.info("✓ Upload verification passed: file found in body -> '%s'", file_name)
            return True

        if attempt < max_checks:
            logger.info("File not visible yet, waiting %dms before rechecking...", interval_ms)
            page.wait_for_timeout(interval_ms)

    logger.warning("✗ Upload verification FAILED: file not found -> '%s'", file_name)
    logger.warning("Expected file: '%s'", file_name)
    logger.warning("Found files: %s", [repr(f) for f in found_files])
    return False
