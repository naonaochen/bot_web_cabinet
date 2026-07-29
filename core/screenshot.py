from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page

from .utils import ensure_dir, now_str, safe_filename


def save_screenshot(page: Page, base_dir: str, name: str) -> str:
    ensure_dir(base_dir)
    filename = f"{now_str()}_{safe_filename(name)}.png"
    path = Path(base_dir) / filename
    
    try:
        if page.is_closed():
            return str(path)
    except Exception as e:
        # If we can't check page state, assume it's closed and return path
        return str(path)

    try:
        page.screenshot(path=str(path), full_page=True)
        return str(path)
    except Exception as e:
        # Log error but still return the expected path for consistency
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("Failed to save screenshot to %s: %s", path, str(e))
        return str(path)
