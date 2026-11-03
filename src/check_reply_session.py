#!/usr/bin/env python3
"""Cek kesehatan sesi reply: buka 1 halaman post, klik affordance Reply dengan
selector PERSIS seperti auto_comment.py (multi-fallback), lalu laporkan:
COMPOSER_OK / LOGIN_WALL / STUB_DELETED / NEITHER.
TIDAK mengetik, TIDAK memposting. Pakai: check_reply_session.py <url-post>"""
import sys, json
from pathlib import Path
BOT = Path(__file__).resolve().parent  # folder instance = lokasi file ini
STATE = BOT / "state.json"
url = sys.argv[1] if len(sys.argv) > 1 else None
if not url:
    q = json.load(open(BOT / "comments.json"))
    url = q[0]["url"] if isinstance(q, list) else q["items"][0]["url"]
from cloakbrowser import launch
browser = launch(headless=True, humanize=True, args=["--fingerprint=71529"])
try:
    ctx = browser.new_context(storage_state=str(STATE))
    page = ctx.new_page()
    page.goto(url, timeout=120000, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    opened = page.evaluate("""() => {
      const sels = [
        '[aria-label="Expand composer"]',
        '[aria-label="Reply"]',
        '[aria-label="Balas"]',
        'svg[aria-label="Reply"]',
        '[role="button"][aria-label*="composer" i]',
        '[role="button"][aria-label*="reply" i]',
        '[role="button"][aria-label*="balas" i]',
      ];
      for (const s of sels) {
        const el = document.querySelector(s);
        if (el) { el.click(); return s; }
      }
      const cands = [...document.querySelectorAll('[role="button"], button, svg')];
      const hit = cands.find(e => {
        const t = (e.getAttribute('aria-label') || e.textContent || '').trim().toLowerCase();
        return t === 'reply' || t === 'balas' || t === 'expand composer';
      });
      if (hit) {
        const target = (typeof hit.click === 'function') ? hit : (hit.closest('[role="button"], button') || hit.parentElement);
        if (target && typeof target.click === 'function') { target.click(); return 'text-fallback'; }
        if (target) {
          target.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
          return 'dispatch-fallback';
        }
      }
      return false;
    }""")
    page.wait_for_timeout(3200)
    st = page.evaluate("""() => {
      const body = document.body.innerText || "";
      const wall = body.includes("Say more with Threads") || body.includes("Log in or sign up for Threads");
      const stub = /post not available|post unavailable|post tidak tersedia/i.test(body) && body.length < 400;
      const expand = !!document.querySelector('[aria-label="Expand composer"]');
      const box = !!document.querySelector('[contenteditable="true"]');
      return {wall: wall, stub: stub, expand: expand, box: box};
    }""")
    if st["wall"]:
        print("LOGIN_WALL: sesi logout, klik Reply memunculkan dinding login (via=%s)" % opened)
    elif st["stub"]:
        print("STUB_DELETED: post sudah tidak tersedia, bukan masalah sesi (via=%s)" % opened)
    elif st["expand"] or st["box"]:
        print("COMPOSER_OK: composer terbuka (via=%s)" % opened)
    else:
        print("NEITHER: tidak ada dinding login, stub, maupun composer (via=%s)" % opened)
finally:
    try: browser.close()
    except Exception: pass
