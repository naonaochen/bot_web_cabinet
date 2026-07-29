from __future__ import annotations

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, expect

from .browser import _force_front_and_maximize

try:
    from .captcha_ocr import OCR_AVAILABLE, recognize_captcha
except Exception:
    OCR_AVAILABLE = False
    recognize_captcha = None


def _set_page_zoom(page: Page, percent: int = 80) -> None:
    import logging
    logger = logging.getLogger(__name__)
    
    zoom = percent / 100.0
    try:
        page.evaluate(
            """
            (z) => {
                try {
                    document.documentElement.style.zoom = String(z);
                    if (document.body) {
                        document.body.style.zoom = String(z);
                    }
                } catch (e) {}
            }
            """,
            zoom,
        )
    except Exception as e:
        logger.warning("Failed to set page zoom to %d%%: %s", percent, str(e))


def _wait_login_success(page: Page, login_cfg: dict) -> None:
    success_texts = login_cfg.get("success_texts", [])
    max_checks = login_cfg.get("max_checks", 60)
    check_interval_ms = login_cfg.get("check_interval_ms", 500)

    for _ in range(max_checks):
        if page.is_closed():
            raise RuntimeError("Login page was closed before success could be confirmed")
        current_url = page.url
        body_text = page.locator("body").inner_text()
        if "#/login" not in current_url:
            return
        if any(text in body_text for text in success_texts):
            return
        page.wait_for_timeout(check_interval_ms)

    raise RuntimeError("Login success page was not detected within timeout")


def _login_success_detected(page: Page, login_cfg: dict) -> bool:
    success_url_fragment = login_cfg.get("success_url_fragment", "")
    success_texts = login_cfg.get("success_texts", [])
    current_url = page.url

    if success_url_fragment and success_url_fragment in current_url:
        return True

    body_text = page.locator("body").inner_text()
    if any(text in body_text for text in success_texts):
        return True

    if "#/login" not in current_url:
        return True

    return False


def _fill_captcha_value(captcha, value: str) -> None:
    captcha.click()
    try:
        captcha.press("Control+A")
    except Exception:
        pass
    captcha.fill(value)
    try:
        captcha.press("Tab")
    except Exception:
        pass


def _handle_manual_captcha(page: Page, login_cfg: dict, config: dict, logger) -> None:
    """
    Handle manual captcha input mode
    
    Waits for user to enter captcha and click login button
    """
    captcha = page.get_by_placeholder(login_cfg["captcha_placeholder"])
    login_btn = page.get_by_role("button", name=login_cfg["login_button_name"])
    
    logger.info("=" * 60)
    logger.warning("ATTENTION: Automatic CAPTCHA recognition stopped")
    logger.warning("Please enter the captcha manually in the browser")
    logger.info("=" * 60)
    logger.info("Manual steps:")
    logger.info("  1. Enter the captcha code")
    logger.info("  2. Click the 'Login' button")
    logger.info("  3. Automation will continue automatically after successful login")
    logger.info("=" * 60)
    
    try:
        captcha.wait_for(state="visible", timeout=30000)
        captcha.click(force=True)
    except Exception:
        pass
    
    try:
        login_btn.scroll_into_view_if_needed(timeout=2000)
    except Exception:
        pass

    captcha_timeout_s = config.get("timeouts", {}).get("captcha_timeout_s", 30)
    check_interval_ms = config.get("timeouts", {}).get("captcha_check_interval_ms", 500)
    max_checks = int(captcha_timeout_s * 1000 / check_interval_ms)
    
    for _ in range(max_checks):
        try:
            if page.is_closed():
                raise RuntimeError("Login page was closed while waiting for captcha input")
            if captcha.input_value().strip():
                break
        except PlaywrightError as e:
            if "closed" in str(e).lower():
                raise RuntimeError("Login page was closed while waiting for captcha input") from e
        except Exception:
            pass
        try:
            page.wait_for_timeout(check_interval_ms)
        except PlaywrightError as e:
            if "closed" in str(e).lower():
                raise RuntimeError("Login page was closed while waiting for captcha input") from e
    else:
        raise RuntimeError("Captcha was not entered within the timeout")


def login(page: Page, config: dict, logger) -> None:
    login_cfg = config["login"]
    app_cfg = config["app"]
    zoom_percent = config.get("ui", {}).get("page_zoom_percent", 80)

    page.goto(app_cfg["url"], wait_until="domcontentloaded")
    try:
        _force_front_and_maximize(page)
        _set_page_zoom(page, zoom_percent)
    except Exception as e:
        logger.warning("Failed to configure browser window: %s", str(e))
    
    login_wait_ms = config.get("timeouts", {}).get("login_wait_ms", 2000)
    page.wait_for_timeout(login_wait_ms)

    username = page.get_by_placeholder(login_cfg["username_placeholder"])
    password = page.get_by_placeholder(login_cfg["password_placeholder"])
    captcha = page.get_by_placeholder(login_cfg["captcha_placeholder"])
    login_btn = page.get_by_role("button", name=login_cfg["login_button_name"])

    expect(username).to_be_visible()
    expect(password).to_be_visible()
    expect(captcha).to_be_visible()
    expect(login_btn).to_be_visible()

    username.fill(login_cfg["username"])
    password.fill(login_cfg["password"])

    # Check if automatic captcha recognition is enabled
    auto_captcha = config.get("login", {}).get("auto_captcha", False)
    
    if auto_captcha and OCR_AVAILABLE:
        logger.info("=" * 60)
        logger.info("Attempting automatic CAPTCHA recognition...")
        logger.info("=" * 60)

        max_ocr_attempts = 1
        captcha_value = None
        for attempt in range(1, max_ocr_attempts + 1):
            logger.info("CAPTCHA OCR attempt %d/%d", attempt, max_ocr_attempts)
            captcha_value = recognize_captcha(page, logger, config)
            if captcha_value:
                break

        if captcha_value:
            logger.info("✓ CAPTCHA recognized successfully: '%s'", captcha_value)
            _fill_captcha_value(captcha, captcha_value)
            logger.info("CAPTCHA value filled into input box")
            login_btn.click()
            page.wait_for_load_state("networkidle")
        else:
            logger.warning(" CAPTCHA recognition failed after %d attempt(s), falling back to manual input", max_ocr_attempts)
            _handle_manual_captcha(page, login_cfg, config, logger)
    elif auto_captcha and not OCR_AVAILABLE:
        logger.warning("Auto captcha requested but OCR libraries not installed")
        logger.warning("Please install: pip install pytesseract pillow")
        logger.warning("Falling back to manual captcha input")
        _handle_manual_captcha(page, login_cfg, config, logger)
    else:
        # Manual captcha mode (default)
        _handle_manual_captcha(page, login_cfg, config, logger)

    _wait_login_success(page, login_cfg)

    final_wait_ms = config.get("timeouts", {}).get("login_final_wait_ms", 3000)
    if not _login_success_detected(page, login_cfg):
        page.wait_for_timeout(final_wait_ms)
        if not _login_success_detected(page, login_cfg):
            raise RuntimeError("Login success could not be confirmed")

    logger.info("Login successful")
