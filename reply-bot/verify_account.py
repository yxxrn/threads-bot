#!/usr/bin/env python3
"""Verifikasi akun sesi instance ini TANPA posting.
Pakai: ./venv/bin/python verify_account.py [--state <file>]
Keluar: MATCH / MISMATCH / UNDETERMINED / STATE_MISSING (+ exit code 0/1/2)."""
import sys, argparse
from pathlib import Path
BOT = Path(__file__).resolve().parent
sys.path.insert(0, str(BOT))
import account_guard
from cloakbrowser import launch
ap = argparse.ArgumentParser()
ap.add_argument("--state", default="state.json")
args = ap.parse_args()
state = BOT / args.state
if not state.exists():
    print(f"STATE_MISSING: {state.name} tidak ada (tidak bisa verifikasi)")
    sys.exit(2)
expected = account_guard.load_expected(BOT)
if not expected:
    print("ACCOUNT_JSON_MISSING: account.json hilang/rusak")
    sys.exit(2)
browser = launch(headless=True, humanize=True, args=["--fingerprint=71529"])
try:
    ctx = browser.new_context(storage_state=str(state))
    page = ctx.new_page()
    ok, exp, found, via = account_guard.verify(page, BOT)
    if ok:
        print(f"MATCH: sesi adalah @{found} (via={via})")
        sys.exit(0)
    elif found is None:
        print(f"UNDETERMINED: expected=@{exp} found=None via={via} (kemungkinan logout)")
        sys.exit(1)
    else:
        print(f"MISMATCH: expected=@{exp} found=@{found} via={via} -- JANGAN POSTING")
        sys.exit(1)
finally:
    try: browser.close()
    except Exception: pass
