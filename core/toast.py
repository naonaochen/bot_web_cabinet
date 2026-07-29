from __future__ import annotations

from playwright.sync_api import Locator, Page

TOAST_SELECTOR = ".el-message--success, .el-message, .el-notification, div[role='alert'].el-message, div[role='alert']"


def dismiss_toasts(page: Page, *, root=None, close_wait_ms: int = 300, settle_ms: int = 800) -> None:
    search_root = root if root is not None else page
    try:
        locator = search_root.locator(TOAST_SELECTOR)
        count = locator.count()
        for idx in range(count - 1, -1, -1):
            try:
                toast = locator.nth(idx)
                if not toast.is_visible():
                    continue
                close_btn = toast.locator(
                    "button, .el-message__closeBtn, .el-notification__closeBtn, [aria-label='Close']"
                ).first
                if close_btn.count() > 0 and close_btn.is_visible():
                    close_btn.click(force=True)
                else:
                    toast.click(force=True)
                page.wait_for_timeout(close_wait_ms)
            except Exception:
                continue
    except Exception:
        pass
    page.wait_for_timeout(settle_ms)


def collect_visible_toast_texts(page: Page, *, root=None) -> list[str]:
    search_root = root if root is not None else page
    try:
        texts = page.evaluate(
            """(sel) => Array.from(document.querySelectorAll(sel))
                .filter(el => {
                    const s = window.getComputedStyle(el);
                    return s.display !== 'none' && s.visibility !== 'hidden';
                })
                .map(el => (el.innerText || el.textContent || '').trim())
                .filter(Boolean)""",
            TOAST_SELECTOR,
        )
        if isinstance(texts, list):
            return [str(t).strip() for t in texts if str(t).strip()]
    except Exception:
        pass

    found: list[str] = []
    try:
        locator = search_root.locator(TOAST_SELECTOR)
        for idx in range(locator.count()):
            try:
                item = locator.nth(idx)
                if item.is_visible():
                    text = item.inner_text().strip()
                    if text:
                        found.append(text)
            except Exception:
                continue
    except Exception:
        pass
    return found


def latest_new_toast(page: Page, baseline_texts: list[str] | None, success_text: str, *, root=None) -> str:
    current_texts = collect_visible_toast_texts(page, root=root)
    if not current_texts:
        return ""
    baseline_set = set(baseline_texts or [])
    new_texts = [t for t in current_texts if t not in baseline_set]
    candidates = new_texts if new_texts else current_texts
    for text in reversed(candidates):
        if success_text and success_text in text:
            return text
    return ""
