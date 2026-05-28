"""Bulk-upload Steam achievements to the Steamworks partner portal.

Reads an achievements CSV and uploads each row (API name, display name,
description, achieved icon, unachieved icon) to the partner portal using
Playwright browser automation.

The browser opens visibly so you can monitor progress and intervene if needed.
Your login session is saved to .playwright_profile/ (or --profile-dir) so you
only need to log in once.

Usage:
    steam-ach-upload <app_id> <csv_file>
    steam-ach-upload <app_id> <csv_file> --start 10   # resume from row 10
    steam-ach-upload <app_id> <csv_file> --dry-run    # print plan, no browser

CSV columns (see sample/achievements.csv for an example):
    API Name          - Steam internal achievement identifier
    Display Name (EN) - Name shown to players
    Description (EN)  - Description shown to players
    Achieved Icon     - Path to the unlocked icon (relative to the CSV file)
    Unachieved Icon   - Path to the locked icon (relative to the CSV file)
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from pathlib import Path

_STEAM_URL = "https://partner.steamgames.com/apps/achievements/{app_id}"


def build_url(app_id: str) -> str:
    return _STEAM_URL.format(app_id=app_id)


def load_achievements(csv_path: Path) -> list[dict]:
    with open(csv_path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


async def _wait_login(page) -> None:
    """Block until the achievements page is ready (user has logged in)."""
    print("\n  Waiting for you to log in …  (continues automatically)\n")
    await page.wait_for_selector("text=New Achievement", timeout=0)
    print("  Logged in — starting upload.\n")


async def _cancel_open_rows(page) -> None:
    """Dismiss any edit rows left open from a previous run or failed upload."""
    cancel_sel = "input[type='submit'][value='Cancel']"
    n = await page.locator(cancel_sel).count()
    if n:
        print(f"  Cancelling {n} leftover open row(s) …")
    for _ in range(n):
        await page.locator(cancel_sel).first.click()
        await page.wait_for_timeout(400)


async def _debug_dump(page) -> None:
    """Click New Achievement, print the new-row HTML, then cancel — for debugging."""
    await _cancel_open_rows(page)
    cancel_sel = "input[type='submit'][value='Cancel']"
    cancel_before = await page.locator(cancel_sel).count()
    await page.locator("input[type='submit'][value='New Achievement']").first.click()
    await page.wait_for_function(
        f"document.querySelectorAll(\"{cancel_sel}\").length > {cancel_before}",
        timeout=10_000,
    )
    container = page.locator(cancel_sel).last.locator("xpath=ancestor::tr[1]")
    try:
        html = await container.inner_html()
        print(f"\n  new row inner HTML:\n{html}\n")
    except Exception as e:
        print(f"  could not get row HTML: {e}")
    try:
        await page.locator(cancel_sel).last.click()
    except Exception:
        pass


async def _add_one(
    page, ach: dict, index: int, total: int, ach_dir: Path
) -> None:
    steam_id    = ach["API Name"]
    name        = ach["Display Name (EN)"]
    description = ach["Description (EN)"]
    icon_done   = ach_dir / ach["Achieved Icon"]
    icon_locked = ach_dir / ach["Unachieved Icon"]

    print(f"  [{index}/{total}] {steam_id}")

    cancel_sel = "input[type='submit'][value='Cancel']"

    await _cancel_open_rows(page)

    # Pass 1: create the record (text fields only — Steam requires a save before
    # file uploads are accepted).
    cancel_before = await page.locator(cancel_sel).count()
    await page.locator("input[type='submit'][value='New Achievement']").first.click()
    await page.wait_for_function(
        f"document.querySelectorAll(\"{cancel_sel}\").length > {cancel_before}",
        timeout=10_000,
    )

    container = page.locator(cancel_sel).last.locator("xpath=ancestor::tr[1]")
    api_input = container.locator("input[id$='_apiname']")
    await api_input.wait_for(state="visible", timeout=5_000)
    await api_input.fill(steam_id)
    await container.locator("form[id$='_displayname'] input[name='english']").fill(name)
    await container.locator("form[id$='_description'] input[name='english']").fill(description)

    await container.locator("input[type='submit'][value='Save']").click()
    await page.wait_for_function(
        f"document.querySelectorAll(\"{cancel_sel}\").length <= {cancel_before}",
        timeout=15_000,
    )
    await page.wait_for_timeout(500)

    # Pass 2: edit the saved row to upload icons.
    row = page.locator("tr").filter(has_text=steam_id).last
    await row.locator("input[type='submit'][value='Edit']").click()
    await page.wait_for_function(
        f"document.querySelectorAll(\"{cancel_sel}\").length > {cancel_before}",
        timeout=10_000,
    )

    container    = page.locator(cancel_sel).last.locator("xpath=ancestor::tr[1]")
    file_inputs  = container.locator("input[type='file']")
    upload_btns  = container.locator("input[type='submit'][value='Upload']")

    await file_inputs.nth(0).set_input_files(str(icon_done))
    await upload_btns.nth(0).click()
    await page.wait_for_timeout(3_000)

    await file_inputs.nth(1).set_input_files(str(icon_locked))
    await upload_btns.nth(1).click()
    await page.wait_for_timeout(3_000)

    await container.locator("input[type='submit'][value='Save']").click()
    await page.wait_for_function(
        f"document.querySelectorAll(\"{cancel_sel}\").length <= {cancel_before}",
        timeout=15_000,
    )
    await page.wait_for_timeout(500)


async def _run(app_id: str, csv_path: Path, profile_dir: Path, start: int) -> None:
    ach_dir      = csv_path.parent
    achievements = load_achievements(csv_path)
    subset       = achievements[start - 1:]
    total        = len(achievements)
    url          = build_url(app_id)

    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            args=["--start-maximized"],
            no_viewport=True,
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto(url)
        await _wait_login(page)
        await _cancel_open_rows(page)

        failed: list[str] = []
        for i, ach in enumerate(subset, start=start):
            try:
                await _add_one(page, ach, i, total, ach_dir)
            except Exception as exc:
                print(f"    ERROR: {exc}")
                print(f"    Re-run with --start {i} to retry from here.")
                failed.append(ach["API Name"])
                try:
                    await page.locator("input[type='submit'][value='Cancel']").last.click()
                except Exception:
                    pass

        await ctx.close()

    done = total - len(failed) - (start - 1)
    print(f"\nDone. {done} added, {len(failed)} failed.")
    if failed:
        print(f"Failed: {', '.join(failed)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "app_id",
        help="Your Steam App ID (e.g. 1234567)",
    )
    parser.add_argument(
        "csv_file",
        type=Path,
        help="Path to the achievements CSV file",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=1,
        metavar="N",
        help="Start from row N of the CSV (1-indexed, default 1)",
    )
    parser.add_argument(
        "--profile-dir",
        type=Path,
        default=Path(".playwright_profile"),
        metavar="DIR",
        help="Directory for the persistent browser session (default: .playwright_profile)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be uploaded without opening a browser",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Open browser, click New Achievement once, print page structure, then exit",
    )
    args = parser.parse_args()

    csv_path    = args.csv_file.resolve()
    profile_dir = args.profile_dir.resolve()

    if not csv_path.exists():
        parser.error(f"CSV file not found: {csv_path}")

    achievements = load_achievements(csv_path)

    if args.debug:
        async def _debug_run() -> None:
            from playwright.async_api import async_playwright
            async with async_playwright() as pw:
                ctx = await pw.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    headless=False,
                    args=["--start-maximized"],
                    no_viewport=True,
                )
                page = ctx.pages[0] if ctx.pages else await ctx.new_page()
                await page.goto(build_url(args.app_id))
                await _wait_login(page)
                await _debug_dump(page)
                input("\n  Press Enter to close the browser …")
                await ctx.close()

        asyncio.run(_debug_run())
        return

    if args.dry_run:
        for i, a in enumerate(achievements[args.start - 1:], start=args.start):
            print(f"  [{i}] {a['API Name']:40s}  {a['Display Name (EN)']}")
        return

    remaining = len(achievements) - args.start + 1
    print(f"Uploading {remaining} achievement(s) (rows {args.start}–{len(achievements)}) to app {args.app_id} …")
    asyncio.run(_run(args.app_id, csv_path, profile_dir, args.start))


if __name__ == "__main__":
    main()
