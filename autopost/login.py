#!/usr/bin/env python3
"""One-time Threads login. Saves cookies to storage_state.json."""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "storage_state.json"
PROFILE = ROOT / "browser-data"


def main() -> None:
    PROFILE.mkdir(exist_ok=True)
    with sync_playwright() as p:
        headed = bool(__import__("os").environ.get("DISPLAY"))
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE),
            headless=not headed,
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://www.threads.net/login", wait_until="domcontentloaded")
        print("Login di browser.")
        print("Setelah feed Threads terbuka, tekan Enter di sini.")
        if not headed:
            print("Headless: set DISPLAY atau pakai CDP remote (lihat README).")
        input()
        page.goto("https://www.threads.net/", wait_until="domcontentloaded")
        ctx.storage_state(path=str(STATE))
        print(f"saved {STATE}")
        ctx.close()


if __name__ == "__main__":
    main()
