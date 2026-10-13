#!/usr/bin/env python3
"""Find recent Threads posts worth replying to (AI-related, <24h old).

Usage:
  ./venv/bin/python find_posts.py --keywords "AI agent,automation,AI tool" --max-age-hours 24 --limit 10
  ./venv/bin/python find_posts.py --keywords "AI" --json   # machine output

Output: JSON array of {url, author, text, age_hours, posted_at, likes, replies}
saved to found_posts.json and printed.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BOT = Path(__file__).resolve().parent
STATE = BOT / "state.json"
OUT = BOT / "found_posts.json"


def scrape_search(page, keyword, max_age_hours, seen):
    """Open search for one keyword, click Recent, scroll, extract posts."""
    import urllib.parse

    url = f"https://www.threads.com/search?q={urllib.parse.quote(keyword)}"
    page.goto(url, timeout=120000, wait_until="domcontentloaded")
    page.wait_for_timeout(4500)

    # klik tab "Recent" (kalau ada)
    try:
        page.evaluate(
            """() => {
                const els = [...document.querySelectorAll('[role=tab],[role=button],a,div')];
                const r = els.find(e => (e.innerText||'').trim() === 'Recent');
                if (r) r.click();
            }"""
        )
        page.wait_for_timeout(3500)
    except Exception:
        pass

    # scroll untuk memuat lebih banyak
    for _ in range(7):
        page.mouse.wheel(0, 3200)
        page.wait_for_timeout(1400)

    posts = page.evaluate(
        """() => {
            const out = [];
            const seenLocal = new Set();
            document.querySelectorAll('a[href*="/post/"]').forEach(a => {
                const href = a.getAttribute('href');
                if (!href || href.endsWith('/media') || seenLocal.has(href)) return;
                seenLocal.add(href);
                // container post
                let el = a, best = null;
                for (let i = 0; i < 14 && el; i++) {
                    el = el.parentElement;
                    if (!el) break;
                    const r = el.getBoundingClientRect();
                    if (r.height > 120 && r.width > 300) {
                        const t = (el.innerText || '').trim();
                        if (t.length > 60) { best = el; break; }
                    }
                }
                if (!best) return;
                const txt = (best.innerText || '').trim();
                const lines = txt.split('\\n').map(s => s.trim()).filter(Boolean);
                const author = lines[0] || '';
                // timestamp: elemen <time> di dalam container
                const tEl = best.querySelector('time');
                const dt = tEl ? tEl.getAttribute('datetime') : null;
                const ageTxt = tEl ? (tEl.innerText || '').trim() : '';
                // metrik: angka-angka di akhir biasanya likes/replies
                const nums = lines.slice(-4).filter(s => /^[\\d.,]+[KM]?$/.test(s));
                // teks post: buang baris author + waktu + metrik
                const bodyLines = lines.filter((s, i) => i > 0 && s !== ageTxt && !/^[\\d.,]+[KM]?$/.test(s));
                out.push({
                    url: 'https://www.threads.com' + href,
                    author,
                    age_text: ageTxt,
                    posted_at: dt,
                    text: bodyLines.join(' ').slice(0, 600),
                    metrics: nums,
                });
            });
            return out;
        }"""
    )

    now = datetime.now(timezone.utc)
    fresh = []
    for p in posts:
        key = p["url"]
        if key in seen:
            continue
        dt = p.get("posted_at")
        age_h = None
        if dt:
            try:
                when = datetime.fromisoformat(dt.replace("Z", "+00:00"))
                age_h = (now - when).total_seconds() / 3600.0
            except Exception:
                age_h = None
        if age_h is None:
            # fallback: parse "6h", "20h", "1d"
            t = (p.get("age_text") or "").strip().lower()
            try:
                if t.endswith("h"):
                    age_h = float(t[:-1])
                elif t.endswith("m"):
                    age_h = float(t[:-1]) / 60.0
                elif t.endswith("d"):
                    age_h = float(t[:-1]) * 24
            except Exception:
                age_h = None
        if age_h is None or age_h > max_age_hours:
            continue
        # Skip posts with no real text (media-only posts can't be replied to
        # naturally — our comment would look disconnected).
        clean = (p.get("text") or "").strip()
        if len(clean) < 40:
            continue
        p["age_hours"] = round(age_h, 2)
        p["keyword"] = keyword
        seen.add(key)
        fresh.append(p)
    return fresh


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--keywords",
        default="AI agent,AI automation,AI tool,build in public AI",
        help="comma-separated search keywords",
    )
    ap.add_argument("--max-age-hours", type=float, default=24)
    ap.add_argument("--limit", type=int, default=10)
    a = ap.parse_args()

    if not STATE.exists():
        print("NO_SESSION: state.json belum ada.")
        return 2

    from cloakbrowser import launch

    kws = [k.strip() for k in a.keywords.split(",") if k.strip()]
    browser = launch(headless=True, args=["--fingerprint=71529"])
    found, seen = [], set()
    # Exclude posts we already replied to or that are queued for retry
    for fname in ("replied_urls.json", "retry_queue.json"):
        fp = BOT / fname
        if fp.exists():
            try:
                data = json.loads(fp.read_text())
                for it in (data if isinstance(data, list) else []):
                    u = it.get("url") if isinstance(it, dict) else it
                    if u:
                        seen.add(u)
            except Exception:
                pass
    try:
        ctx = browser.new_context(storage_state=str(STATE))
        page = ctx.new_page()
        for kw in kws:
            if len(found) >= a.limit:
                break
            try:
                batch = scrape_search(page, kw, a.max_age_hours, seen)
                found.extend(batch)
                print(f"[{kw}] +{len(batch)} posts (total {len(found)})", file=sys.stderr)
            except Exception as e:
                print(f"[{kw}] error: {e}", file=sys.stderr)
        found = found[: a.limit]
    finally:
        try:
            browser.close()
        except Exception:
            pass

    OUT.write_text(json.dumps(found, ensure_ascii=False, indent=1))
    print(json.dumps(found, ensure_ascii=False, indent=1))
    print(f"\nSAVED: {OUT} ({len(found)} posts)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
