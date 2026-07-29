from __future__ import annotations

from playwright.sync_api import Locator, Page, expect

from .toast import collect_visible_toast_texts, dismiss_toasts, latest_new_toast
from .utils import find_row_by_text


def _click_text_button(
    page: Page,
    button_text: str,
    *,
    timeout_ms: int = 5000,
    force: bool = True,
    scope=None,
) -> bool:
    root = scope if scope is not None else page
    candidates = [
        root.get_by_role("button", name=button_text),
        root.get_by_text(button_text, exact=True),
    ]
    for candidate in candidates:
        try:
            n = candidate.count()
            if n == 0:
                continue
            for idx in range(n):
                item = candidate.nth(idx)
                try:
                    if not item.is_visible():
                        continue
                    button = item.locator("xpath=ancestor-or-self::button[1]")
                    if button.count() == 0:
                        button = item
                    target = button.first
                    if target.is_visible():
                        target.click(force=force, timeout=timeout_ms)
                        return True
                except Exception:
                    continue
        except Exception:
            continue
    return False


def _resolve_apply_button(row: Locator, apply_text: str) -> Locator | None:
    candidates = [
        row.locator("button.el-button--primary").filter(has_text=apply_text),
        row.get_by_role("button", name=apply_text),
        row.locator(f"button:has-text('{apply_text}')"),
        row.get_by_text(apply_text, exact=True),
    ]
    for cand in candidates:
        try:
            if cand.count() > 0 and cand.first.is_visible():
                return cand.first
        except Exception:
            continue
    return None


def _button_state(btn: Locator) -> tuple[bool, bool]:
    try:
        visible = btn.is_visible()
    except Exception:
        visible = False
    try:
        enabled = btn.is_enabled() if visible else False
    except Exception:
        enabled = False
    return visible, enabled


def apply_file(page: Page, target_file_name: str, config: dict, logger) -> None:
    """Apply the target file and confirm success mainly via new toast."""
    apply_cfg = config["apply"]
    row_selector = config["search"]["result_row_selector"]
    apply_text = apply_cfg["apply_button_text"]
    success_text = apply_cfg.get("success_toast_text", "Apply Para Success")
    started_text = apply_cfg.get("started_toast_text", "Start Application")
    apply_wait_ms = int(config.get("timeouts", {}).get("apply_wait_ms", 5000))

    rows = page.locator(row_selector)
    if rows.count() == 0:
        raise ValueError("No rows found on upload page")

    target_row = find_row_by_text(rows, target_file_name)
    if target_row is None:
        raise ValueError(f"Target file not found: {target_file_name}")

    apply_btn = _resolve_apply_button(target_row, apply_text)
    if apply_btn is None:
        apply_btn = target_row.get_by_text(apply_text, exact=True)
    expect(apply_btn).to_be_visible()
    expect(apply_btn).to_be_enabled()
    logger.info("Found Apply button for '%s' - currently enabled", target_file_name)

    dismiss_toasts(page)
    baseline = collect_visible_toast_texts(page)

    try:
        apply_btn.click(force=True)
    except Exception:
        if not _click_text_button(page, apply_text, scope=target_row, force=True):
            raise RuntimeError(f"Apply button for '{target_file_name}' could not be clicked")
    logger.info("Apply button clicked for: %s", target_file_name)

    page.wait_for_timeout(apply_wait_ms)

    matched = latest_new_toast(page, baseline, success_text)
    if matched or latest_new_toast(page, baseline, started_text):
        logger.info("Apply success via new toast for %s: %s", target_file_name, matched or started_text)
        dismiss_toasts(page)
        logger.info("Apply operation completed for: %s", target_file_name)
        return

    try:
        rows_after = page.locator(row_selector)
        row_after = find_row_by_text(rows_after, target_file_name)
        if row_after is None:
            logger.warning("Target row not found after apply for %s", target_file_name)
        else:
            btn_after = _resolve_apply_button(row_after, apply_text)
            if btn_after is None:
                logger.info("Apply control no longer found for %s - treating as success", target_file_name)
            else:
                visible, enabled = _button_state(btn_after)
                if visible and not enabled:
                    logger.info("Apply button disabled for %s - fallback success", target_file_name)
                elif not visible:
                    logger.info("Apply button hidden for %s - fallback success", target_file_name)
                else:
                    page.wait_for_timeout(1500)
                    matched = latest_new_toast(page, baseline, success_text)
                    if matched or latest_new_toast(page, baseline, started_text):
                        logger.info("Apply success via toast after retry for %s", target_file_name)
                    else:
                        _, enabled2 = _button_state(btn_after)
                        if not enabled2:
                            logger.info("Apply button disabled after wait for %s", target_file_name)
                        else:
                            logger.error("Apply still enabled and no new success toast for %s", target_file_name)
                            raise RuntimeError(
                                f"Apply for '{target_file_name}' not confirmed (no new toast / button still enabled)"
                            )
    except RuntimeError:
        raise
    except Exception as e:
        logger.warning("Could not verify Apply state: %s", str(e))
        logger.info("Continuing with automation...")

    dismiss_toasts(page)
    logger.info("Apply operation completed for: %s", target_file_name)


def has_new_apply_success_toast(
    page: Page,
    success_text: str = "Apply Para Success",
    started_text: str = "Start Application",
    baseline: list[str] | None = None,
) -> bool:
    return bool(latest_new_toast(page, baseline, success_text) or latest_new_toast(page, baseline, started_text))
