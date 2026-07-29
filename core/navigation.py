from __future__ import annotations

from playwright.sync_api import Page, expect


def _click_menu_path(page: Page, path: list[str], logger) -> None:
    logger.info("Starting to click menu path: %s", " > ".join(path))

    def _click_visible(locator, menu_text: str, label: str) -> bool:
        count = locator.count()
        logger.info("  Found %d element(s) with %s text '%s'", count, label, menu_text)
        for idx in range(count):
            item = locator.nth(idx)
            try:
                if item.is_visible():
                    logger.info("  Element is visible, clicking...")
                    item.click(force=True)
                    logger.info("  ✓ Clicked menu (%s): %s", label, menu_text)
                    return True
            except Exception:
                continue
        return False

    def _click_expandable_parent(text_locator, menu_text: str) -> bool:
        count = text_locator.count()
        for idx in range(count):
            item = text_locator.nth(idx)
            try:
                ancestors = item.locator("xpath=ancestor::*[self::a or self::button or self::li or self::div]")
                ancestor_count = ancestors.count()
                for aidx in range(ancestor_count):
                    ancestor = ancestors.nth(aidx)
                    try:
                        if ancestor.is_visible():
                            logger.info("  Trying expandable parent for '%s'", menu_text)
                            ancestor.click(force=True)
                            logger.info("  ✓ Clicked expandable parent for: %s", menu_text)
                            return True
                    except Exception:
                        continue
            except Exception:
                continue
        return False

    for i, menu_text in enumerate(path):
        logger.info("[%d/%d] Attempting to click menu: '%s'", i + 1, len(path), menu_text)
        clicked = False

        if i < len(path) - 1:
            next_menu_text = path[i + 1]
            try:
                next_visible = any(page.locator(f"text={next_menu_text}").nth(idx).is_visible() for idx in range(page.locator(f"text={next_menu_text}").count()))
            except Exception:
                next_visible = False
            if next_visible:
                logger.info("  Next menu '%s' is already visible; skipping click on '%s'", next_menu_text, menu_text)
                continue

        try:
            logger.info("  Trying exact match for: '%s'", menu_text)
            exact_menu = page.get_by_text(menu_text, exact=True)
            if _click_visible(exact_menu, menu_text, "exact"):
                clicked = True
            else:
                raise Exception("Exact match locator hidden or not clickable")
        except Exception as e:
            logger.warning("  Exact match failed: %s", str(e))
            try:
                logger.info("  Trying partial match for: '%s'", menu_text)
                partial_menu = page.locator(f"text={menu_text}")
                if _click_visible(partial_menu, menu_text, "partial"):
                    clicked = True
                else:
                    raise Exception("Partial match locator hidden or not clickable")
            except Exception as e2:
                logger.warning("  Partial match failed: %s", str(e2))
                try:
                    logger.info("  Trying expandable-parent fallback for: '%s'", menu_text)
                    if _click_expandable_parent(page.locator(f"text={menu_text}"), menu_text):
                        clicked = True
                    else:
                        raise Exception(f"No visible expandable parent found for '{menu_text}'")
                except Exception as e3:
                    logger.error("  ✗ Failed to click menu '%s': %s", menu_text, str(e3))
                    try:
                        debug_screenshot = f"debug_menu_{menu_text.replace(' ', '_')}.png"
                        page.screenshot(path=debug_screenshot)
                        logger.info("  Debug screenshot saved: %s", debug_screenshot)
                    except Exception:
                        pass
                    raise RuntimeError(f"Could not find or click menu: {menu_text}") from e3

        if not clicked:
            raise RuntimeError(f"Could not find or click menu: {menu_text}")

        logger.info("  Waiting for navigation to complete...")
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
            logger.info("  ✓ Navigation completed")
        except Exception as e:
            logger.warning("   Network idle timeout: %s", str(e))
            logger.info("  Continuing anyway after 1 second wait...")
            page.wait_for_timeout(1000)

        if i < len(path) - 1:
            logger.info("  Waiting for submenu to appear...")
            page.wait_for_timeout(500)

    logger.info("✓ All menus clicked successfully: %s", " > ".join(path))


def navigate_to_target(page: Page, config: dict, logger) -> None:
    nav_cfg = config["navigation"]
    overview_text = nav_cfg.get("overview_menu_text", "Overview")
    menus = nav_cfg.get("menus", [])

    # Wait for page to be ready after login
    page.wait_for_timeout(2000)
    
    # Try to find Overview menu with flexible matching
    try:
        overview = page.get_by_text(overview_text, exact=True)
        expect(overview).to_be_visible(timeout=5000)
        logger.info("Found Overview menu (exact match)")
    except Exception:
        # Fallback: try partial match
        try:
            overview = page.locator(f"text={overview_text}").first
            expect(overview).to_be_visible(timeout=5000)
            logger.info("Found Overview menu (partial match)")
        except Exception as e:
            logger.warning(f"Could not find Overview menu: {e}")
            logger.info("Continuing anyway...")

    _click_menu_path(page, menus, logger)
    logger.info("Navigation completed: %s", " > ".join([overview_text] + menus))


def navigate_to_setting_south_communication(page: Page, config: dict, logger) -> None:
    nav_cfg = config["navigation"]
    path = nav_cfg.get("settings_menu_path", ["Setting", "South Communication"])

    overview = page.get_by_text(nav_cfg.get("overview_menu_text", "Overview"), exact=True)
    expect(overview).to_be_visible()

    _click_menu_path(page, path, logger)
    logger.info("Navigation completed: %s", " > ".join(path))
