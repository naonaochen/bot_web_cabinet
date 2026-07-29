from __future__ import annotations

import os
from pathlib import Path
from shutil import which

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright


def _force_front_and_maximize(page: Page) -> None:
    import logging
    logger = logging.getLogger(__name__)
    
    # Note: This function doesn't have access to config, using hardcoded defaults
    # For better design, consider passing config or timeout values as parameters
    max_attempts = 3
    wait_ms = 500  # Increased wait time for better reliability
    
    for attempt in range(max_attempts):
        try:
            # Bring browser to front
            page.bring_to_front()
            logger.info("Attempt %d: Bringing browser to front...", attempt + 1)
            
            # Try multiple methods to maximize
            page.evaluate(
                """
                () => {
                    try {
                        // Method 1: Move to top-left and resize to full screen
                        window.moveTo(0, 0);
                        window.resizeTo(screen.availWidth, screen.availHeight);
                        
                        // Method 2: Request fullscreen (may require user interaction)
                        if (document.documentElement.requestFullscreen) {
                            document.documentElement.requestFullscreen().catch(() => {});
                        }
                        
                        // Method 3: Set body to full viewport
                        document.body.style.width = '100vw';
                        document.body.style.height = '100vh';
                        document.body.style.margin = '0';
                        document.body.style.padding = '0';
                    } catch (e) {
                        console.log('Maximize attempt failed:', e);
                    }
                }
                """
            )
            
            # Wait for changes to take effect
            page.wait_for_timeout(wait_ms)
            
            # Verify window size
            window_size = page.evaluate("() => ({ width: window.innerWidth, height: window.innerHeight })")
            logger.info("Window size after maximize attempt: %dx%d", window_size['width'], window_size['height'])
            
            # If window is reasonably large, consider it successful
            if window_size['width'] >= 1280 and window_size['height'] >= 720:
                logger.info("✓ Browser window maximized successfully")
                return  # Success, exit early
                
        except Exception as e:
            logger.warning("Attempt %d to bring browser to front failed: %s", attempt + 1, str(e))
            if attempt == max_attempts - 1:  # Last attempt
                logger.error("Failed to bring browser to front after %d attempts", max_attempts)
    
    logger.warning("Browser maximize completed with warnings")


def _browser_executable_path() -> str | None:
    appdata = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        Path(appdata) / "ms-playwright" / "chromium-1187" / "chrome-win" / "chrome.exe",
        Path(appdata) / "ms-playwright" / "chromium" / "chrome-win" / "chrome.exe",
        Path(appdata) / "Playwright" / "chromium-1187" / "chrome-win" / "chrome.exe",
        Path(appdata) / "Playwright" / "chromium" / "chrome-win" / "chrome.exe",
        Path(appdata) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
    ]

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    for name in ("chrome", "msedge", "chromium"):
        found = which(name)
        if found:
            return found

    return None


def create_browser(config: dict) -> tuple:
    app = config["app"]
    files = config["files"]

    Path(files["trace_dir"]).mkdir(parents=True, exist_ok=True)

    playwright = sync_playwright().start()
    browser_type = getattr(playwright, app.get("browser", "chromium"))

    browser_channel = app.get("browser_channel", "chrome")
    executable_path = _browser_executable_path()
    browser_launch_kwargs = {
        "headless": app.get("headless", False),
        "args": [
            "--start-maximized",
            "--disable-infobars",
            "--no-first-run",
            "--disable-session-crashed-bubble",
            "--disable-extensions",
        ],
    }

    if browser_channel in {"chrome", "msedge"}:
        browser_launch_kwargs["channel"] = browser_channel
    elif executable_path:
        browser_launch_kwargs["executable_path"] = executable_path

    browser: Browser = browser_type.launch(**browser_launch_kwargs)

    # Create context with no fixed viewport to allow full screen
    context: BrowserContext = browser.new_context(
        locale="zh-CN",
        accept_downloads=True,
        ignore_https_errors=True,
        no_viewport=True,  # Important: allows window to use full screen
    )
    context.set_default_timeout(app.get("timeout_ms", 30000))
    context.tracing.start(screenshots=True, snapshots=True, sources=True)

    page: Page = context.new_page()
    
    # Force maximize after page creation
    try:
        _force_front_and_maximize(page)
        logger = logging.getLogger(__name__)
        logger.info("Browser window maximization attempted")
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("Failed to maximize browser: %s", str(e))
    
    return playwright, browser, context, page
