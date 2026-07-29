from __future__ import annotations

from playwright.sync_api import Page, expect

from .utils import get_safe_row_text


def _find_visible_locator(page: Page, selectors: list[str], scope=None):
    root = scope if scope is not None else page
    for selector in selectors:
        locator = root.locator(selector)
        if locator.count() == 0:
            continue
        for i in range(locator.count()):
            item = locator.nth(i)
            try:
                if item.is_visible():
                    return item
            except Exception:
                continue
    return None


def _select_device_type(page: Page, device_type_value: str, logger) -> None:
    section_candidates = [
        "text=Setting->South Communication",
        "text=South Communication",
        "div:has-text('Setting->South Communication')",
        "div:has-text('South Communication')",
        "main",
        "body",
    ]
    control_candidates = [
        "label:has-text('Device Type') + * div.el-select",
        "label:has-text('Device Type') + * [role='combobox']",
        "label:has-text('Device Type') + * input[readonly]",
        "label:has-text('Device Type') + * select",
        "label:has-text('Device Type') ~ div.el-select",
        "label:has-text('Device Type') ~ [role='combobox']",
        "div.el-select",
        "div[role='combobox']",
        "span.el-input__inner",
        "input[readonly]",
        "select",
    ]

    section = None
    for selector in section_candidates:
        candidate = page.locator(selector)
        if candidate.count() == 0:
            continue
        for i in range(candidate.count()):
            item = candidate.nth(i)
            try:
                if item.is_visible():
                    section = item
                    break
            except Exception:
                continue
        if section is not None:
            break

    control = _find_visible_locator(page, control_candidates, scope=section)
    if control is None:
        control = _find_visible_locator(page, control_candidates)
    if control is None:
        raise RuntimeError("Could not locate visible Device Type control")

    tag = ""
    try:
        tag = control.evaluate("el => el.tagName.toLowerCase()")
    except Exception:
        tag = ""

    try:
        if tag == "select":
            control.select_option(label=device_type_value)
            logger.info("Device Type selected by <select>: %s", device_type_value)
            return
    except Exception:
        pass

    try:
        control.scroll_into_view_if_needed(timeout=3000)
    except Exception:
        pass

    control.click(force=True)
    page.wait_for_timeout(500)

    option_candidates = [
        f"li:has-text('{device_type_value}')",
        f"div:has-text('{device_type_value}')",
        f"span:has-text('{device_type_value}')",
        f"text={device_type_value}",
    ]

    for selector in option_candidates:
        option = page.locator(selector)
        if option.count() == 0:
            continue
        for i in range(option.count()):
            item = option.nth(i)
            try:
                if item.is_visible():
                    item.click(force=True)
                    logger.info("Device Type selected via popup option: %s", device_type_value)
                    return
            except Exception:
                continue

    raise RuntimeError(f"Could not select Device Type value: {device_type_value}")


def set_south_communication(page: Page, config: dict, logger) -> None:
    cfg = config["south_communication"]

    _select_device_type(page, cfg["device_type_value"], logger)

    save_btn = page.get_by_text(cfg["save_button_text"], exact=True)
    expect(save_btn).to_be_visible()
    save_btn.click()
    
    # Use configurable wait time after save
    south_comm_wait_ms = config.get("timeouts", {}).get("south_comm_wait_ms", 2000)
    page.wait_for_timeout(south_comm_wait_ms)
    
    logger.info("South Communication values selected and saved")


def ensure_only_device_type_row(page: Page, config: dict, logger) -> None:
    """
    Keep only rows where Device Type is "IOB_Protocol_V1.0"
    Delete all other rows by clicking the Del button
    """
    cfg = config["south_communication"]
    delete_text = cfg.get("delete_button_text", "Del")
    target_device_type = cfg.get("target_row_device_type", "IOB_Protocol_V1.0")
    
    logger.info("=" * 60)
    logger.info("Cleaning South Communication table...")
    logger.info("Keeping only Device Type: '%s'", target_device_type)
    logger.info("Deleting all other device types")
    logger.info("=" * 60)

    # Wait for table to be fully loaded
    page.wait_for_timeout(1000)
    
    rows = page.locator("table tbody tr")
    row_count = rows.count()
    
    if row_count == 0:
        logger.warning("No rows found in South Communication table")
        return
    
    logger.info("Found %d row(s) in table", row_count)
    
    # Log all current rows for debugging
    for i in range(row_count):
        row = rows.nth(i)
        row_text = get_safe_row_text(row)
        logger.info("  Row %d: '%s'", i+1, row_text)
    
    # Collect rows to delete (work backwards to avoid index shifting)
    rows_to_delete = []
    for i in range(row_count - 1, -1, -1):  # Iterate backwards
        row = rows.nth(i)
        row_text = get_safe_row_text(row)
        
        if not row_text:
            continue
        
        # Check if this row contains the target device type
        if target_device_type in row_text:
            logger.info("  ✓ Keeping row %d (contains '%s')", i+1, target_device_type)
            continue
        else:
            logger.info("  ✗ Marking row %d for deletion (Device Type: '%s')", i+1, row_text.split()[0] if row_text else "unknown")
            rows_to_delete.append(i)
    
    # Delete marked rows
    if rows_to_delete:
        logger.info("")
        logger.info("Deleting %d row(s)...", len(rows_to_delete))
        
        for row_idx in sorted(rows_to_delete, reverse=True):  # Delete from bottom to top
            try:
                row = rows.nth(row_idx)
                row_text = get_safe_row_text(row)
                
                # Find and click the Del button
                del_btn = row.get_by_text(delete_text, exact=True)
                
                if del_btn.count() > 0:
                    logger.info("  Deleting row %d: '%s'", row_idx + 1, row_text[:50] if row_text else "unknown")
                    del_btn.first.click(force=True)
                    
                    # Wait for deletion to complete
                    row_check_interval_ms = config.get("timeouts", {}).get("row_check_interval_ms", 1000)
                    page.wait_for_timeout(row_check_interval_ms)
                    
                    # Refresh row locator after deletion
                    rows = page.locator("table tbody tr")
                else:
                    logger.warning("  No 'Del' button found for row %d", row_idx + 1)
                    
            except Exception as e:
                logger.error("  Failed to delete row %d: %s", row_idx + 1, str(e))
    else:
        logger.info("✓ No rows to delete - all rows have correct Device Type")
    
    # Verify final state
    page.wait_for_timeout(500)
    rows = page.locator("table tbody tr")
    final_count = rows.count()
    
    logger.info("")
    logger.info("Final verification:")
    logger.info("  Total rows remaining: %d", final_count)
    
    for i in range(final_count):
        row = rows.nth(i)
        row_text = get_safe_row_text(row)
        if target_device_type in row_text:
            logger.info("  ✓ Row %d: Contains '%s' (correct)", i+1, target_device_type)
        else:
            logger.warning("  ✗ Row %d: Does NOT contain '%s' (unexpected!)", i+1, target_device_type)
            logger.warning("    Row text: '%s'", row_text)
    
    logger.info("=" * 60)
    logger.info("✓ South Communication table cleanup completed")
    logger.info("=" * 60)
