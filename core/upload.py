from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page, expect


def upload_file(page: Page, file_path: str, config: dict, logger) -> str:
    upload_cfg = config["upload"]
    path_obj = Path(file_path)
    resolved_path = str(path_obj if path_obj.is_absolute() else Path.cwd() / path_obj)
    
    logger.info("Attempting to upload file: '%s'", resolved_path)

    add_btn = page.get_by_text(upload_cfg["add_button_text"], exact=True)
    expect(add_btn).to_be_visible()

    file_input_selector = upload_cfg.get("file_input_selector", "input[type='file']")
    file_input = page.locator(file_input_selector)

    if file_input.count() > 0:
        try:
            file_input.first.set_input_files(resolved_path)
            logger.info("✓ File selected via hidden input: %s", resolved_path)
            return resolved_path
        except Exception as e:
            logger.warning("Hidden input upload failed (%s), fallback to file chooser dialog", str(e))

    logger.info("Using file chooser dialog for upload...")
    with page.expect_file_chooser() as chooser_info:
        add_btn.click()

    file_chooser = chooser_info.value
    file_chooser.set_files(resolved_path)
    logger.info("✓ File selected via file chooser dialog: %s", resolved_path)
    return resolved_path
