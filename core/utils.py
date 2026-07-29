from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.error import URLError, HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import ssl
import sys

import yaml
from playwright.sync_api import Locator


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", project_root()))
    return project_root()


def resolve_path(path: str | Path) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    
    # For frozen apps (EXE), first check the directory where EXE is located
    # This allows users to place settings.yaml next to the EXE file
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        config_path = exe_dir / p
        if config_path.exists():
            return config_path
    
    # Fallback to bundle_root for packaged resources or source code
    return bundle_root() / p


def load_config(path: str = "config/settings.yaml") -> dict:
    config_path = resolve_path(path)
    
    # If config file doesn't exist, return empty config with defaults
    if not config_path.exists():
        print(f"[WARN] Config file not found: {config_path}")
        print("[INFO] Using default configuration. Please create settings.yaml in the EXE directory.")
        return _get_default_config()
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        # Validate required configuration sections
        _validate_config(config)
        return config
    except Exception as e:
        print(f"[ERROR] Failed to load config from {config_path}: {e}")
        print("[INFO] Using default configuration instead.")
        return _get_default_config()


def _validate_config(config: dict) -> None:
    """
    Validate that all required configuration sections and keys exist.
    
    Args:
        config: Loaded configuration dictionary
        
    Raises:
        ValueError: If required configuration is missing or invalid
    """
    required_sections = {
        "app": ["url", "headless", "timeout_ms", "browser"],
        "login": ["username", "password", "login_button_name", "success_texts"],
        "navigation": ["menus", "calibration_menu_path", "active_alarm_menu_path"],
        "search": ["result_row_selector"],
        "upload": ["add_button_text", "file_input_selector"],
        "apply": ["target_file_name", "apply_button_text"],
        "delete": ["delete_button_text", "confirm_button_text"],
        "south_communication": ["device_type_value", "target_row_fields", "save_button_text", "delete_button_text"],
        "calibration": ["reset_delay_ms", "visible_progress_ms"],
        "files": ["input_excel", "screenshot_dir", "trace_dir", "log_dir"],
    }
    
    for section, required_keys in required_sections.items():
        if section not in config:
            raise ValueError(f"Missing required configuration section: '{section}'")
        
        for key in required_keys:
            if key not in config[section]:
                raise ValueError(f"Missing required key '{key}' in section '{section}'")
    
    # Validate URL format
    app_url = config["app"]["url"]
    if not app_url.startswith(("http://", "https://")):
        raise ValueError(f"Invalid URL format in app.url: {app_url}")
    
    # Validate timeout values are positive integers
    timeout = config["app"]["timeout_ms"]
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        raise ValueError(f"Invalid timeout_ms value: {timeout} (must be positive number)")
    
    reset_delay = config["calibration"]["reset_delay_ms"]
    if not isinstance(reset_delay, (int, float)) or reset_delay < 0:
        raise ValueError(f"Invalid calibration.reset_delay_ms value: {reset_delay} (must be non-negative number)")


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def now_str() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def safe_filename(text: str) -> str:
    invalid = '<>:"/\\|?*'
    for ch in invalid:
        text = text.replace(ch, "_")
    return text.strip().replace(" ", "_")


def check_url_reachable(url: str, timeout: int = 5) -> tuple[bool, str]:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return False, f"Invalid URL: {url}"

    probe_url = f"{parsed.scheme}://{parsed.netloc}"
    context = ssl._create_unverified_context()
    request = Request(probe_url, method="GET", headers={"User-Agent": "Mozilla/5.0"})

    try:
        with urlopen(request, timeout=timeout, context=context) as response:
            return True, f"HTTP {response.status}"
    except HTTPError as e:
        return True, f"HTTP {e.code}"
    except URLError as e:
        return False, str(e.reason)
    except Exception as e:
        return False, str(e)


def find_row_by_text(rows: Locator, search_text: str) -> Optional[Locator]:
    """
    Find a table row containing the specified text.
    
    Args:
        rows: Locator for table rows (e.g., page.locator("table tbody tr"))
        search_text: Text to search for in row content
        
    Returns:
        Locator for the matching row, or None if not found
    """
    row_count = rows.count()
    for i in range(row_count):
        row = rows.nth(i)
        try:
            row_text = row.inner_text().strip()
            if search_text in row_text:
                return row
        except Exception:
            continue
    return None


def get_safe_row_text(row: Locator) -> str:
    """
    Safely extract text from a table row with fallback methods.
    
    Args:
        row: Locator for a table row
        
    Returns:
        Stripped text content, or empty string if extraction fails
    """
    try:
        return row.inner_text(timeout=2000).strip()
    except Exception:
        try:
            return row.evaluate("el => el.innerText || el.textContent || '').strip()")
        except Exception:
            return ""


def _get_default_config() -> dict:
    """
    Return default configuration when settings.yaml is not found.
    This allows the EXE to start even without a config file.
    
    Returns:
        dict: Default configuration with minimal required settings
    """
    return {
        "app": {
            "url": "https://192.168.70.2/#/login",
            "headless": False,
            "timeout_ms": 30000,
            "browser": "chromium",
            "browser_channel": "chrome",
        },
        "login": {
            "username": "admin",
            "password": "654321",
            "login_type": "Local",
            "captcha_value": "",
            "auto_captcha": True,
            "manual_captcha": False,
        },
        "ui": {
            "page_zoom_percent": 100,
            "initial_width": 400,
            "initial_height": 300,
            "min_width": 400,
            "min_height": 300,
            "start_shrink_width": 400,
            "start_shrink_height": 300,
            "idle_alpha": 0.75,
        },
        "navigation": {
            "overview_menu_text": "Overview",
            "main_menu_texts": ["Status", "Active Alarm", "Setting", "Control", "Records", "Assets", "User", "Maintenance"],
            "menus": ["Maintenance", "Download/Upload"],
        },
        "upload": {
            "add_button_text": "ADD",
            "file_input_selector": "input[type='file']",
        },
        "apply": {
            "target_file_name": "VF3-Outdoor Test-V0.csv",
            "apply_button_text": "Apply",
        },
        "delete": {
            "delete_button_text": "Delete",
        },
        "flow": {
            "upload_files": [],
            "apply_target_file": "VF3-Outdoor Test-V0.csv",
        },
        "files": {
            "input_excel": "data/input.xlsx",
            "screenshot_dir": "screenshots",
            "trace_dir": "traces",
            "log_dir": "logs",
        },
        "timeouts": {
            "login_wait_ms": 2000,
            "captcha_timeout_s": 30,
            "apply_wait_ms": 3000,
        },
    }
