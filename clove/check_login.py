#!/usr/bin/env python3
"""Verify the saved Threads session (state.json). Prints only status/handle."""
from __future__ import annotations

import sys
from pathlib import Path

BOT = Path(__file__).resolve().parent
STATE = BOT / "state.json"


def main() -> int:
    if not STATE.exists():
        print("NO_SESSION: state.json belum ada — jalankan login.py dulu.")
        return 2
    from cloakbrowser import launch

    browser = launch(headless=True, args=["--fingerprint=71529"])
    try:
        ctx = browser.new_context(storage_state=str(STATE))
        page = ctx.new_page()
        page.goto(
            "https://www.threads.com/",
            timeout=120000,
            wait_until="domcontentloaded",
        )
        page.wait_for_timeout(3500)
        try:
            has_login = page.locator("text=Log in").first.is_visible(timeout=1500)
        except Exception:
            has_login = False
        handle = ""
        try:
            hrefs = page.eval_on_selector_all(
                "nav a[href^='/@'], a[href^='/@']",
                "els => els.map(e => e.getAttribute('href'))",
            )
            if hrefs:
                handle = hrefs[0].split("/")[1]
        except Exception:
            pass
        print("LOGGED_IN:", (not has_login))
        if handle:
            print("HANDLE:", handle)
        print("URL:", page.url)
        return 0 if not has_login else 1
    finally:
        try:
            browser.close()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
