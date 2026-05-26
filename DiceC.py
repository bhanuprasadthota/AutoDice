#!/usr/bin/env python3
"""Dice.com Easy Apply automation bot."""

import asyncio
import csv
import os
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urljoin

from playwright.async_api import async_playwright, Page

from config import DICE_EMAIL, DICE_PASSWORD, JOB_TITLES, LOCATION


MAX_APPLICATIONS = int(os.getenv("AUTODICE_MAX_APPLICATIONS", "0") or "0")
DEBUG_DIR = Path(os.getenv("AUTODICE_DEBUG_DIR", "autodice-debug"))
LOG_DIR = Path(os.getenv("AUTODICE_LOG_DIR", "autodice-logs"))
LOG_FILE = LOG_DIR / "applications.csv"
LOG_MAX_BYTES = int(os.getenv("AUTODICE_MAX_LOG_BYTES", str(5 * 1024 * 1024)))
LOG_COLUMNS = ["timestamp", "role", "link", "title", "status", "message"]


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
    "button:has(span:has-text('Submit Application'))",
    "button:has-text('Submit Application')",
    "button:has-text('Submit')",
    "button[data-react-aria-pressable='true']:has-text('Submit')",
    "button.ja-submit-btn",
    "button[type='submit']",
    "//button[contains(., 'Submit')]",
]

NEXT_SELECTORS = [
    "button:has-text('Next')",
    "button:has-text('Continue')",
    "button:has-text('Review')",
    "button:has-text('Review Application')",
    "button.btn-next",
    "//button[contains(., 'Next')]",
    "//button[contains(., 'Continue')]",
    "//button[contains(., 'Review')]",
]

CONFIRMATION_SELECTORS = [
    "p.app-text",
    "text=/application submitted/i",
    "text=/successfully applied/i",
    "text=/you applied/i",
    "text=/already applied/i",
]


class ApplicationLog:
    """CSV-backed record of visited jobs so future runs can skip them."""

    def __init__(self, path: Path = LOG_FILE, max_bytes: int = LOG_MAX_BYTES):
        self.path = path
        self.max_bytes = max_bytes
        self.path.parent.mkdir(exist_ok=True)
        self._ensure_current_file()

    def processed_links(self) -> set[str]:
        links: set[str] = set()
        for csv_path in sorted(self.path.parent.glob("applications*.csv")):
            try:
                with csv_path.open(newline="", encoding="utf-8") as file:
                    for row in csv.DictReader(file):
                        link = row.get("link")
                        if link:
                            links.add(link)
            except Exception as exc:
                print(f"  ⚠  Could not read log {csv_path}: {exc}")
        return links

    def append(self, role: str, link: str, title: str, status: str, message: str = "") -> None:
        self._rotate_if_needed()
        with self.path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=LOG_COLUMNS)
            writer.writerow(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "role": role,
                    "link": link,
                    "title": title,
                    "status": status,
                    "message": message,
                }
            )

    def _ensure_current_file(self) -> None:
        if not self.path.exists() or self.path.stat().st_size == 0:
            with self.path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=LOG_COLUMNS)
                writer.writeheader()

    def _rotate_if_needed(self) -> None:
        if self.path.stat().st_size < self.max_bytes:
            return

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rotated = self.path.with_name(f"{self.path.stem}_{stamp}{self.path.suffix}")
        suffix = 1
        while rotated.exists():
            rotated = self.path.with_name(
                f"{self.path.stem}_{stamp}_{suffix}{self.path.suffix}"
            )
            suffix += 1

        self.path.rename(rotated)
        print(f"  🗂  Log reached {self.max_bytes} bytes; started {self.path}")
        self._ensure_current_file()


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
            if await btn.get_attribute("disabled") is not None:
                await asyncio.sleep(0.25)
                continue

            if await btn.is_enabled():
                await btn.click()
                return True

        except Exception:
            await asyncio.sleep(0.25)

    return False


async def has_confirmation(page: Page) -> bool:
    """Return whether Dice is showing an applied/submitted confirmation."""
    for sel in CONFIRMATION_SELECTORS:
        try:
            if await page.locator(sel).first.is_visible(timeout=500):
                return True
        except Exception:
            continue
    return False


async def dump_application_state(page: Page, title: str) -> None:
    """Print enough UI state to diagnose current Dice application DOM changes."""
    DEBUG_DIR.mkdir(exist_ok=True)
    safe_title = "".join(ch if ch.isalnum() else "-" for ch in title)[:60].strip("-")
    screenshot = DEBUG_DIR / f"{safe_title or 'application'}-stuck.png"
    try:
        await page.screenshot(path=str(screenshot), full_page=True)
        print(f"  🧭 Debug screenshot: {screenshot}")
    except Exception:
        pass

    try:
        buttons = await page.locator("button, a[role='button'], input[type='submit']").evaluate_all(
            """els => els
                .filter(el => {
                    const style = window.getComputedStyle(el);
                    const box = el.getBoundingClientRect();
                    return style.visibility !== 'hidden'
                        && style.display !== 'none'
                        && box.width > 0
                        && box.height > 0;
                })
                .slice(0, 30)
                .map(el => ({
                    text: (el.innerText || el.value || el.getAttribute('aria-label') || '').trim(),
                    disabled: el.disabled || el.getAttribute('aria-disabled') || el.getAttribute('data-disabled') || '',
                    pending: el.getAttribute('data-pending') || ''
                }))"""
        )
        print("  🧭 Visible actions:")
        for button in buttons:
            text = button.get("text") or "<no text>"
            disabled = button.get("disabled") or "false"
            pending = button.get("pending") or "false"
            print(f"     - {text[:80]} | disabled={disabled} pending={pending}")
    except Exception:
        pass

    try:
        fields = await page.locator("input, textarea, select").evaluate_all(
            """els => els
                .filter(el => {
                    const type = (el.getAttribute('type') || '').toLowerCase();
                    if (['hidden', 'submit', 'button'].includes(type)) return false;
                    const style = window.getComputedStyle(el);
                    const box = el.getBoundingClientRect();
                    return style.visibility !== 'hidden'
                        && style.display !== 'none'
                        && box.width > 0
                        && box.height > 0;
                })
                .slice(0, 30)
                .map(el => ({
                    tag: el.tagName.toLowerCase(),
                    type: el.getAttribute('type') || '',
                    name: el.getAttribute('name') || '',
                    label: el.getAttribute('aria-label') || el.placeholder || '',
                    required: el.required || el.getAttribute('aria-required') || ''
                }))"""
        )
        if fields:
            print("  🧭 Visible fields:")
            for field in fields:
                label = field.get("label") or field.get("name") or "<unnamed>"
                print(
                    f"     - {field.get('tag')} {field.get('type')} {label[:80]} "
                    f"required={field.get('required') or 'false'}"
                )
    except Exception:
        pass


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
                await page.wait_for_timeout(1000)
                if await has_confirmation(page):
                    return "applied", None, "Already applied"
                return "easy_apply", btn, None

        await page.wait_for_timeout(500)

    return "none", None, None


async def collect_job_links(page: Page) -> list[str]:
    """Scrape job card links from all result pages for the current search."""
    all_links: list[str] = []
    seen_links: set[str] = set()
    page_num = 1
    print(f"  📄 Page {page_num}")

    while True:
        cards = page.locator("a[data-testid='job-search-job-detail-link']")
        for i in range(await cards.count()):
            link = await cards.nth(i).get_attribute("href")
            if link:
                full_link = urljoin(page.url, link)
                if "/job-detail/" in full_link and full_link not in seen_links:
                    all_links.append(full_link)
                    seen_links.add(full_link)

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


async def enable_easy_apply_filter(page: Page) -> bool:
    """Open Dice filters and turn on Easy apply, verifying the URL flag."""
    try:
        await page.locator("button:has-text('All filters')").click()
        easy_apply = page.locator("label:has-text('Easy apply')").first

        if await easy_apply.count() == 0:
            print("  ⚠  Easy apply filter not found")
            return False
        if await easy_apply.get_attribute("data-disabled") == "true":
            print("  ⚠  Easy apply filter is disabled for this search")
            return False

        await easy_apply.click()
        await page.locator("button:has-text('Apply filters')").click()
        await page.wait_for_timeout(1500)

        if "filters.easyApply=true" not in page.url:
            print("  ⚠  Easy apply filter did not appear in URL")
            return False

        return True
    except Exception as exc:
        print(f"  ⚠  Could not set Easy apply filter: {exc}")
        return False


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
        if aria == "true" or pending == "true":
            print("  ⚠  Submit is disabled/pending")
            return False
    except Exception:
        pass

    if not await click_when_enabled(submit_btn, timeout_ms=30000):
        print("  ⚠  Submit never became clickable")
        return False

    await page.wait_for_timeout(2000)

    if await has_confirmation(page):
        print("  ✅ Submitted!")
        return True

    print("  ⚠  Submit clicked but confirmation not detected")
    return False


async def apply_to_job(page: Page, link: str, role: str) -> dict[str, str]:
    """Navigate to a single job listing and attempt Easy Apply."""
    try:
        await page.goto(link, timeout=15000)
    except Exception:
        print("  ❌ Page failed to load")
        return {"title": role, "status": "load_failed", "message": "Page failed to load"}

    title_el = page.locator("h1[data-cy='jobTitle']")
    title = (await title_el.inner_text()).strip() if await title_el.count() else role
    print(f"  💼 {title}")

    state, btn, msg = await get_apply_button(page)

    if state == "applied":
        print(f"  ✔  {msg}")
        return {"title": title, "status": "already_applied", "message": msg or ""}
    if state == "none":
        print("  ❌ No Easy Apply button found")
        return {"title": title, "status": "no_easy_apply", "message": "No Easy Apply button found"}

    # Wait for the UI to fully settle — Dice sometimes shows "Applied" a beat after load
    await page.wait_for_timeout(1200)
    if await has_confirmation(page):
        print("  ✔  Already applied (detected after page settle)")
        return {
            "title": title,
            "status": "already_applied",
            "message": "Detected after page settle",
        }

    try:
        await btn.click()
    except Exception:
        print("  ❌ Apply button disappeared before click")
        return {
            "title": title,
            "status": "apply_button_disappeared",
            "message": "Apply button disappeared before click",
        }

    await page.wait_for_timeout(1500)

    for _ in range(4):
        if await has_confirmation(page):
            print("  ✅ Submitted!")
            return {"title": title, "status": "submitted", "message": "Submitted"}

        if await try_submit(page):
            return {"title": title, "status": "submitted", "message": "Submitted"}

        for sel in NEXT_SELECTORS:
            next_btn = page.locator(sel).first
            if await click_when_enabled(next_btn, timeout_ms=3000):
                await page.wait_for_timeout(1500)
                break
        else:
            break

    await dump_application_state(page, title)
    print("  ⚠  Could not complete submission — moving on")
    return {
        "title": title,
        "status": "stuck",
        "message": "Could not complete submission",
    }


async def run(playwright) -> None:
    browser = await playwright.chromium.launch(headless=False)
    page = await browser.new_page()
    seen: set[str] = set()  # deduplicate across role searches within a session
    application_log = ApplicationLog()
    logged_links = application_log.processed_links()
    print(f"🧾 Loaded {len(logged_links)} previously logged job links")

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
    applied_count = 0
    for role in JOB_TITLES:
        print(f"🔍 {role}")

        await page.goto(f"https://www.dice.com/jobs?q={role}&location={LOCATION}")
        await page.wait_for_timeout(2000)

        # Filter to Easy Apply jobs only
        if not await enable_easy_apply_filter(page):
            print("  ⚠  Skipping search because Easy Apply is unavailable\n")
            continue

        links = await collect_job_links(page)
        skipped_session = sum(1 for link in links if link in seen)
        skipped_logged = sum(1 for link in links if link in logged_links)
        new_links = [
            link for link in links if link not in seen and link not in logged_links
        ]
        seen.update(new_links)
        print(
            f"  {len(new_links)} new  |  {skipped_session} seen this session"
            f"  |  {skipped_logged} in CSV log\n"
        )

        for idx, link in enumerate(new_links, 1):
            if MAX_APPLICATIONS and applied_count >= MAX_APPLICATIONS:
                print(f"\n🛑 Reached AUTODICE_MAX_APPLICATIONS={MAX_APPLICATIONS}")
                await browser.close()
                return

            print(f"[{idx}/{len(new_links)}] {link}")
            result = await apply_to_job(page, link, role)
            application_log.append(
                role=role,
                link=link,
                title=result["title"],
                status=result["status"],
                message=result["message"],
            )
            logged_links.add(link)
            applied_count += 1

    await browser.close()
    print("\n🎉 All done!")


async def main() -> None:
    async with async_playwright() as pw:
        await run(pw)


if __name__ == "__main__":
    asyncio.run(main())
