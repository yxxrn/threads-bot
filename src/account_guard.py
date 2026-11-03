"""Penjaga identitas akun untuk poster Threads.

Insiden 2026-11-03: daemon panah memposting sebagai @blooplyy_ karena file
state.json-nya berisi sesi akun blooply (tersalin saat transplantasi cookies
2 Nov 2026). Sejak itu, SETIAP konteks browser WAJIB membuktikan bahwa akun
yang login == akun yang ditugaskan ke instance ini, SEBELUM posting apa pun.

Aturan fail-closed (gagal = tidak posting, daemon keluar):
- account.json hilang/rusak -> TOLAK.
- state.json hilang -> TOLAK.
- handle yang terbaca dari navigasi != handle yang ditugaskan -> TOLAK.
- handle tidak bisa ditentukan (dinding login / DOM tak dikenali) -> TOLAK.

Modul ini HANYA membaca navigasi home dan DOM; tidak mengetik, tidak memposting.
"""
from __future__ import annotations
import json
from pathlib import Path

HOME_URL = "https://www.threads.com/"

def load_expected(bot_dir: Path):
    p = bot_dir / "account.json"
    try:
        data = json.loads(p.read_text())
        h = (data.get("handle") or "").strip().lstrip("@").lower()
        return h or None
    except Exception:
        return None

def detect_handle(page):
    """Baca handle akun yang login dari tautan profil di navigasi.
    Mengembalikan (handle_atau_None, metode). Hanya tautan di dalam <nav> atau
    di luar <article> yang dipakai, supaya tautan penulis di feed tidak pernah
    disangka sebagai akun sendiri."""
    page.goto(HOME_URL, timeout=120000, wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    found = page.evaluate("""() => {
      const parse = (h) => {
        if (!h) return null;
        const parts = h.split("/");
        if (parts.length === 2 && parts[0] === "" && parts[1].startsWith("@")) {
          return parts[1].slice(1).toLowerCase();
        }
        return null;
      };
      const prof = document.querySelector('a[aria-label="Profile"]')
        || document.querySelector('a[aria-label="Profil"]');
      if (prof) { const h = parse(prof.getAttribute("href")); if (h) return {handle: h, via: "aria-profile"}; }
      const navs = [...document.querySelectorAll('nav a[href^="/@"]')];
      for (const a of navs) { const h = parse(a.getAttribute("href")); if (h) return {handle: h, via: "nav"}; }
      // Tautan feed BUKAN bukti login (pelajaran 2026-11-03: guard terkecoh tautan
      // feed saat sesi sudah logout). Hanya tautan profil navigasi yang sah.
      const all = [...document.querySelectorAll('a[href^="/@"]')];
      if (all.length > 0) return {handle: null, via: "feed-only"};
      const body = document.body.innerText || "";
      const wall = body.includes("Say more with Threads") || body.includes("Log in or sign up for Threads");
      return {handle: null, via: wall ? "login-wall" : "undetermined"};
    }""")
    return found.get("handle"), found.get("via", "?")

def verify(page, bot_dir: Path):
    """Kembalikan (ok, expected, found, via). ok True HANYA bila found == expected."""
    expected = load_expected(bot_dir)
    if not expected:
        return False, None, None, "account.json-missing"
    found, via = detect_handle(page)
    if not found:
        return False, expected, None, via
    return (found == expected), expected, found, via
