from __future__ import annotations

from playwright.sync_api import Page, expect

from .toast import collect_visible_toast_texts, dismiss_toasts, latest_new_toast
from .utils import find_row_by_text, get_safe_row_text


def _split_filename(value: str) -> str:
    return value.replace("\\", "/").rsplit("/", 1)[-1].strip()


def _extract_filename_from_row_text(row_text: str) -> str:
    if not row_text:
        return ""
    parts = [part.strip() for part in row_text.splitlines() if part.strip()]
    for part in parts:
        if "." in part and not part.isdigit():
            return _split_filename(part)
    tokens = [token.strip() for token in row_text.split() if token.strip()]
    for token in tokens:
        if "." in token and not token.isdigit():
            return _split_filename(token)
    return _split_filename(row_text)


def delete_record(page: Page, target_file_name: str, config: dict, logger) -> None:
    delete_cfg = config["delete"]
    row_selector = config["search"]["result_row_selector"]

    rows = page.locator(row_selector)
    row_count = rows.count()
    if row_count == 0:
        raise ValueError(f"No rows found for file={target_file_name}")

    target_row = find_row_by_text(rows, target_file_name)
    if target_row is None:
        logger.warning("Target file not found, skip delete: %s", target_file_name)
        return

    delete_btn = target_row.get_by_text(delete_cfg["delete_button_text"], exact=True)
    expect(delete_btn).to_be_visible()
    expect(delete_btn).to_be_enabled()

    dismiss_toasts(page)
    baseline = collect_visible_toast_texts(page)

    delete_btn.click(force=True)
    confirm_btn = page.get_by_text(delete_cfg["confirm_button_text"], exact=True)
    expect(confirm_btn).to_be_visible()
    confirm_btn.click(force=True)

    delete_wait_ms = config.get("timeouts", {}).get("delete_verify_wait_ms", 3000)
    page.wait_for_timeout(delete_wait_ms)

    success_text = delete_cfg.get("success_message_text", "")
    if success_text:
        matched = latest_new_toast(page, baseline, success_text)
        if matched:
            logger.info("Delete success toast detected for file=%s: %s", target_file_name, matched)
            return
    logger.info("Delete action triggered for file=%s", target_file_name)


def keep_only_uploaded_files(page: Page, config: dict, logger, uploaded_files: list[str]) -> list[str]:
    delete_cfg = config["delete"]
    delete_button_text = delete_cfg.get("delete_button_text", "Delete")
    confirm_button_text = delete_cfg.get("confirm_button_text", "OK")
    row_selector = config.get("search", {}).get("result_row_selector", "table tbody tr")

    logger.info("=" * 60)
    logger.info("Cleaning Download/Upload table...")
    logger.info("Keeping only uploaded files: %s", uploaded_files)
    logger.info("Deleting all other files")
    logger.info("=" * 60)

    page.wait_for_timeout(1000)
    dismiss_toasts(page)
    baseline = collect_visible_toast_texts(page)

    rows = page.locator(row_selector)
    row_count = rows.count()
    if row_count == 0:
        logger.warning("No files found in Download/Upload table")
        return []

    logger.info("Found %d file(s) in table", row_count)
    all_files = []
    for i in range(row_count):
        row = rows.nth(i)
        row_text = get_safe_row_text(row)
        row_name = _extract_filename_from_row_text(row_text)
        all_files.append(row_text)
        logger.info("  Row %d: '%s' -> file='%s'", i + 1, row_text, row_name)

    keep_names = {_split_filename(item) for item in uploaded_files if item}
    rows_to_delete = []
    deleted_files: list[str] = []
    for i in range(row_count - 1, -1, -1):
        row = rows.nth(i)
        row_text = get_safe_row_text(row)
        row_name = _extract_filename_from_row_text(row_text)
        if not row_text:
            continue
        if row_name in keep_names:
            logger.info("  ✓ Keeping row %d: '%s'", i + 1, row_name)
            continue
        if row_name:
            logger.info("   Marking row %d for deletion: '%s'", i + 1, row_name)
        else:
            logger.info("   Marking row %d for deletion", i + 1)
        rows_to_delete.append(i)

    if rows_to_delete:
        logger.info("")
        logger.info("Deleting %d file(s)...", len(rows_to_delete))
        logger.info("Adding visual delay so user can see each deletion")

        for row_idx in sorted(rows_to_delete, reverse=True):
            try:
                row = rows.nth(row_idx)
                row_text = get_safe_row_text(row)
                delete_btn = row.get_by_text(delete_button_text, exact=True)
                if delete_btn.count() > 0:
                    current_name = _extract_filename_from_row_text(row_text)
                    logger.info("  Deleting row %d: '%s'", row_idx + 1, current_name or row_text[:80] if row_text else "unknown")
                    delete_btn.first.click(force=True)
                    logger.info("    → Delete button clicked")
                    page.wait_for_timeout(500)
                    confirm_btn = page.get_by_text(confirm_button_text, exact=True)
                    if confirm_btn.count() > 0:
                        confirm_btn.first.click(force=True)
                        logger.info("    → Confirmed deletion (OK clicked)")
                    else:
                        logger.warning("    → No confirm button found, deletion may have auto-confirmed")
                    visual_delay_ms = config.get("timeouts", {}).get("delete_visual_delay_ms", 1500)
                    logger.info("    → Waiting %dms for visual feedback...", visual_delay_ms)
                    page.wait_for_timeout(visual_delay_ms)
                    deleted_files.append(current_name or row_text)
                    rows = page.locator(row_selector)
                else:
                    logger.warning("  No 'Delete' button found for row %d", row_idx + 1)
            except Exception as e:
                logger.error("  Failed to delete row %d: %s", row_idx + 1, str(e))
    else:
        logger.info("✓ No files to delete - all files are uploaded files")

    page.wait_for_timeout(500)
    rows = page.locator(row_selector)
    final_count = rows.count()
    logger.info("")
    logger.info("Final verification:")
    logger.info("  Total files remaining: %d", final_count)

    for i in range(final_count):
        row = rows.nth(i)
        row_text = get_safe_row_text(row)
        is_uploaded = False
        for uploaded_file in uploaded_files:
            filename_only = uploaded_file.split("/")[-1].split("\\")[-1]
            if filename_only in row_text or uploaded_file in row_text:
                is_uploaded = True
                logger.info("  ✓ Row %d: '%s' (uploaded file)", i + 1, filename_only)
                break
        if not is_uploaded:
            logger.warning("  ✗ Row %d: '%s' (unexpected file!)", i + 1, row_text)

    success_text = delete_cfg.get("success_message_text", "")
    if success_text:
        matched = latest_new_toast(page, baseline, success_text)
        if matched:
            logger.info("Cleanup success toast detected: %s", matched)

    logger.info("=" * 60)
    logger.info("✓ Download/Upload table cleanup completed")
    logger.info("  Kept %d uploaded file(s)", len(uploaded_files))
    logger.info("  Deleted %d other file(s)", len(rows_to_delete))
    logger.info("=" * 60)
    return deleted_files
