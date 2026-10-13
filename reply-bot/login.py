#!/usr/bin/env python3
"""Interactive one-time login to Threads using CloakBrowser (stealth browser).

Run this YOURSELF on the VPS terminal:

    cd ~/threads-bot && ./venv/bin/python login.py

You will be asked for your Threads/Instagram username and password.
Typing happens in YOUR terminal only (password hidden) — it is never sent to
the chat and the agent never sees it. If Meta asks for a 2FA/security code,
the script asks for it in the same terminal.

On success the session is saved to state.json (chmod 600) next to this script.
After that no more logins are needed until the session expires.
"""
from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path

BOT = Path(__file__).resolve().parent
STATE = BOT / "state.json"
SHOTS = BOT / "shots"
SHOTS.mkdir(exist_ok=True)


def ensure_display():
    """Re-exec under Xvfb so the browser runs headed (less bot-like)."""
    if os.environ.get("DISPLAY"):
        return
    if not os.path.exists("/usr/bin/xvfb-run"):
        os.environ["CLOAK_HEADLESS_FALLBACK"] = "1"
        return
    os.execvp(
        "xvfb-run",
        ["xvfb-run", "-a", "-s", "-screen 0 1366x768x24", sys.executable, *sys.argv],
    )


def shot(page, name):
    try:
        page.screenshot(path=str(SHOTS / f"{name}.png"))
    except Exception:
        pass


def click_first(page, selectors, timeout=1200):
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=timeout):
                loc.click()
                return sel
        except Exception:
            continue
    return None


def main() -> int:
    ensure_display()
    from cloakbrowser import launch

    headless = bool(os.environ.get("CLOAK_HEADLESS_FALLBACK"))
    print("== Threads login via CloakBrowser ==")
    print("(ketikan tidak dikirim ke chat; password disembunyikan)\n")

    username = input("Username / email / phone Threads: ").strip()
    if not username:
        print("Batal: username kosong.")
        return 2
    password = getpass.getpass("Password: ")
    if not password:
        print("Batal: password kosong.")
        return 2

    try:
        browser = launch(headless=headless, humanize=True)
    except TypeError:
        browser = launch(headless=headless)

    try:
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(
            "https://www.threads.com/login",
            timeout=120000,
            wait_until="domcontentloaded",
        )
        page.wait_for_timeout(2500)
        shot(page, "01_login")

        u = page.locator("input[type='text'], input[name='username']").first
        u.click()
        u.fill(username)
        p = page.locator("input[type='password']").first
        p.click()
        p.fill(password)
        page.wait_for_timeout(400)
        click_first(
            page,
            [
                "button[type='submit']",
                "input[type='submit']",
                "div[role='button']:has-text('Log in')",
            ],
        )

        logged_in = False
        for i in range(40):
            page.wait_for_timeout(1500)
            url = page.url
            try:
                body = page.inner_text("body")[:4000]
            except Exception:
                body = ""
            low = body.lower()
            shot(page, f"step_{i:02d}")

            # --- captcha: cannot be solved automatically ---
            if any(k in low for k in ["captcha", "recaptcha", "verify you're human", "bukan robot", "verifikasi bahwa kamu"]):
                print("Terdeteksi captcha di halaman login.")
                print("Solusi: pakai Cara B (kirim file cookies) — atau coba lagi nanti.")
                return 5

            # --- login approval via app/phone: just wait ---
            if any(k in low for k in ["approve", "setujui", "notifikasi", "notification"]):
                print("-> Approve login-nya di app Instagram/Threads di HP-mu. Menunggu...")
                page.wait_for_timeout(8000)
                continue

            # --- 2FA / verification code ---
            if any(
                k in low
                for k in [
                    "two-factor",
                    "2fa",
                    "verification code",
                    "kode verifikasi",
                    "security code",
                    "kode keamanan",
                    "enter the code",
                    "masukkan kode",
                    "we sent",
                    "kami mengirim",
                    "check your email",
                    "cek email",
                ]
            ) or any(k in url for k in ["challenge", "two_factor", "twofactor"]):
                code = input("Kode verifikasi/2FA (email/authenticator/SMS): ").strip()
                filled = False
                for sel in [
                    "input[autocomplete='one-time-code']",
                    "input[name='verificationCode']",
                    "input[inputmode='numeric']",
                    "input[type='tel']",
                    "input[type='text']",
                ]:
                    try:
                        loc = page.locator(sel).first
                        if loc.is_visible(timeout=700):
                            loc.fill(code)
                            filled = True
                            break
                    except Exception:
                        continue
                if filled:
                    click_first(
                        page,
                        [
                            "button[type='submit']",
                            "button:has-text('Next')",
                            "button:has-text('Continue')",
                            "button:has-text('Lanjut')",
                            "div[role='button']:has-text('Next')",
                        ],
                    )
                continue

            # --- dialogs ---
            if any(k in low for k in ["save your login", "simpan info login", "save login info"]):
                click_first(
                    page,
                    [
                        "button:has-text('Not now')",
                        "div[role='button']:has-text('Not now')",
                        "button:has-text('Nanti')",
                    ],
                )
                continue

            # --- hard errors ---
            if any(
                k in low
                for k in [
                    "incorrect",
                    "salah",
                    "couldn't find",
                    "tidak dapat menemukan",
                    "try again later",
                ]
            ):
                print("Login gagal. Pesan halaman:", body[:300].replace("\n", " "))
                return 3

            # --- success check ---
            if "/login" not in url and "threads.com" in url:
                try:
                    has_login = page.locator("text=Log in").first.is_visible(timeout=800)
                except Exception:
                    has_login = False
                if not has_login:
                    logged_in = True
                    break

        if not logged_in:
            print("Status tidak pasti. URL terakhir:", page.url)
            print("Screenshot debugging ada di:", SHOTS)
            return 4

        page.wait_for_timeout(2500)
        click_first(
            page,
            [
                "button:has-text('Not now')",
                "div[role='button']:has-text('Not now')",
                "button:has-text('Nanti')",
            ],
            timeout=600,
        )

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

        ctx.storage_state(path=str(STATE))
        try:
            os.chmod(STATE, 0o600)
        except Exception:
            pass
        shot(page, "99_logged_in")
        print("\nLOGIN OK" + (f" sebagai @{handle}" if handle else ""))
        print("Sesi disimpan ke:", STATE)
        print("Sekarang bilang ke agent: 'login selesai' — lanjut verifikasi.")
        return 0
    finally:
        try:
            browser.close()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
