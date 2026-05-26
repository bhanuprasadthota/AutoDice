#!/usr/bin/env python3
"""Dice.com Easy Apply automation bot."""

import asyncio
from playwright.async_api import async_playwright, Page

from config import DICE_EMAIL, DICE_PASSWORD, JOB_TITLES, LOCATION


# Selectors for the Easy Apply / Apply button
APPLY_SELECTORS = [
    "a[data-testid='apply-button']:has-text('Easy Apply')",
    "a[data-testid='apply-button']:has-text('Apply')",
    "a:has-text('Easy Apply')",
    "a:has-text('Apply')",
    "a.apply-button_applyButton__4HXTr",
    "button.btn-primary:has-text('Easy apply')",
    "button:has-text('Easy Apply')",
    "button:has-text('Easy apply')",
    "//button[contains(., 'Easy apply')]",
    "//a[contains(., 'Easy Apply')]",
    "//a[contains(., 'Apply')]",
    "//button[contains(., 'Easy Apply')]",
    "//button[contains(., 'Apply')]",
]

# Selectors for the final Submit button
SUBMIT_SELECTORS = [
    "button:has(span:has-text('Submit'))",
    "button:has-text('Submit')",
    "button[data-react-aria-pressable='true']:has-text('Submit')",
    "button.ja-submit-btn",
    "button[type='submit']",
    "//button[contains(., 'Submit')]",
]


async def click_when_enabled(locator, timeout_ms: int = 20000) -> bool:
    """Poll until the locator is enabled and not aria-disabled, then click it."""
    deadline = asyncio.get_running_loop().time() + timeout_ms / 1000

    while asyncio.get_running_loop().time() < deadline:
        try:
            if await locator.count() == 0:
                await asyncio.sleep(0.25)
                continue

            btn = locator.first
            await btn.scroll_into_view_if_needed()

            if await btn.get_attribute("aria-disabled") == "true":
                await asyncio.sleep(0.25)
                continue

            if await btn.is_enabled():
                await btn.click()
                return True

        except Exception:
            await asyncio.sleep(0.25)

    return False


async def get_apply_button(page: Page) -> tuple:
    """Return (state, button, message).

    state values:
      'applied'    — already applied, nothing to do
      'easy_apply' — Easy Apply button found and ready
      'none'       — no applicable button found
    """
    for _ in range(12):  # poll up to ~6 s
        if await page.locator("p.app-text").count() > 0:
            date_el = page.locator("span.app-date")
            date = (
                await date_el.get_attribute("title")
                if await date_el.count() > 0
                else "unknown date"
            )
            return "applied", None, f"Already applied on {date}"

        for sel in APPLY_SELECTORS:
            btn = page.locator(sel).first
            if await btn.count() > 0 and await btn.is_visible():
                return "easy_apply", btn, None

        await page.wait_for_timeout(500)

    return "none", None, None


async def collect_job_links(page: Page) -> list[str]:
    """Scrape job card links from all result pages for the current search."""
    all_links: set[str] = set()
    page_num = 1
    print(f"  📄 Page {page_num}")

    while True:
        cards = page.locator("a[data-testid='job-search-job-detail-link']")
        for i in range(await cards.count()):
            link = await cards.nth(i).get_attribute("href")
            if link:
                all_links.add(link)

        next_btn = page.locator("span[aria-label='Next']")

        if not await next_btn.is_visible():
            break
        if (
            await next_btn.get_attribute("aria-disabled") == "true"
            or await next_btn.get_attribute("data-disabled") == "true"
        ):
            break

        try:
            await next_btn.click()
        except Exception:
            break

        page_num += 1
        print(f"  📄 Page {page_num}")
        await page.wait_for_timeout(2000)

    return list(all_links)


async def try_submit(page: Page) -> bool:
    """Locate the Submit button, wait for it to be enabled, click, and verify confirmation."""
    submit_btn = None
    for sel in SUBMIT_SELECTORS:
        try:
            candidate = page.locator(sel)
            if await candidate.count() > 0 and await candidate.first.is_visible():
                submit_btn = candidate.first
                break
        except Exception:
            continue

    if not submit_btn:
        return False

    try:
        aria = await submit_btn.get_attribute("aria-disabled")
        pending = await submit_btn.get_attribute("data-pending")
        if str(aria).lower() == "true" or str(pending).lower() == "true":
            print("  ⚠  Submit is disabled/pending")
            return False
    except Exception:
        pass

    if not await click_when_enabled(submit_btn, timeout_ms=30000):
        print("  ⚠  Submit never became clickable")
        return False

    await page.wait_for_timeout(2000)

    if await page.locator("p.app-text").count() > 0:
        print("  ✅ Submitted!")
        return True

    print("  ⚠  Submit clicked but confirmation not detected")
    return False


async def apply_to_job(page: Page, link: str, role: str) -> None:
    """Navigate to a single job listing and attempt Easy Apply."""
    try:
        await page.goto(link, timeout=15000)
    except Exception:
        print("  ❌ Page failed to load")
        return

    title_el = page.locator("h1[data-cy='jobTitle']")
    title = (await title_el.inner_text()).strip() if await title_el.count() else role
    print(f"  💼 {title}")

    state, btn, msg = await get_apply_button(page)

    if state == "applied":
        print(f"  ✔  {msg}")
        return
    if state == "none":
        print("  ❌ No Easy Apply button found")
        return

    # Wait for the UI to fully settle — Dice sometimes shows "Applied" a beat after load
    await page.wait_for_timeout(1200)
    if await page.locator("p.app-text").count() > 0:
        print("  ✔  Already applied (detected after page settle)")
        return

    try:
        await btn.click()
    except Exception:
        print("  ❌ Apply button disappeared before click")
        return

    await page.wait_for_timeout(1500)

    # Attempt 1: submit on the current page
    if await try_submit(page):
        return

    # Attempt 2: advance one page then submit (some flows have a review step)
    next_btn = page.locator(
        "button:has-text('Next'), button:has-text('Continue'), button.btn-next"
    ).first
    if await click_when_enabled(next_btn, timeout_ms=5000):
        await page.wait_for_timeout(1500)
        if await try_submit(page):
            return

    print("  ⚠  Could not complete submission — moving on")


async def run(playwright) -> None:
    browser = await playwright.chromium.launch(headless=False)
    page = await browser.new_page()
    seen: set[str] = set()  # deduplicate across role searches within a session

    # ── Login ──────────────────────────────────────────────────────────────
    await page.goto("https://www.dice.com/dashboard/login")
    await page.fill("input[type=email]", DICE_EMAIL)
    await page.click("button[type=submit]")
    await page.wait_for_timeout(1500)
    await page.fill("input[type=password]", DICE_PASSWORD)
    await page.click("button[type=submit]")
    await page.wait_for_load_state("networkidle")
    print("✔  Logged in\n")

    # ── Search & apply ─────────────────────────────────────────────────────
    for role in JOB_TITLES:
        print(f"🔍 {role}")

        await page.goto(f"https://www.dice.com/jobs?q={role}&location={LOCATION}")
        await page.wait_for_timeout(2000)

        # Filter to Easy Apply jobs only
        try:
            await page.locator("button:has-text('All filters')").click()
            await page.locator("label:has-text('Easy Apply')").click()
            await page.locator("button:has-text('Apply filters')").click()
            await page.wait_for_timeout(1500)
        except Exception:
            pass

        links = await collect_job_links(page)
        new_links = [l for l in links if l not in seen]
        seen.update(new_links)

        skipped = len(links) - len(new_links)
        print(f"  {len(new_links)} new  |  {skipped} already seen this session\n")

        for idx, link in enumerate(new_links, 1):
            print(f"[{idx}/{len(new_links)}] {link}")
            await apply_to_job(page, link, role)

    await browser.close()
    print("\n🎉 All done!")


async def main() -> None:
    async with async_playwright() as pw:
        await run(pw)


if __name__ == "__main__":
    asyncio.run(main())
