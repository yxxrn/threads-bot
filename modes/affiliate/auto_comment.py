#!/usr/bin/env python3
"""Full-auto reply pipeline v3 (continuous mode) + top-reply model v2.

Queue (processed in order, deduped per part: main key = plain URL, extra
key = URL + "#top_reply"):
  1. retry_queue.json — posts that failed a previous attempt (max 2 tries)
  2. comments.json    — fresh batch written by the cycle agent

Per item: main reply to the post ALWAYS, then (model v2) an EXTRA reply to
the current top reply when the thread is busy (>= busy_threshold replies,
default 20, judged at posting time). Extra falls back to the top reply
visible at posting time; a skip-category top reply skips only the extra.
  1. retry_queue.json — posts that failed a previous attempt (max 2 tries)
  2. comments.json    — fresh batch written by the cycle agent

Per post: open page -> "Expand composer" modal -> attach promo.jpg via CDP ->
type (Playwright native + real Enter x2 = genuine blank line) -> Post -> verify.
Gaps between posts: 120-180s random (user setting). No daily cap; a 24h session
window (session.json) auto-stops the bot when elapsed. Bookkeeping: posted_history.jsonl (append-only),
replied_urls.json (successful URLs), retry_queue.json (auto-managed),
auto_log.json (this run). Idempotent: skips posts whose comment is already on
the page (self-heals false-negative verifications from previous runs).
"""
from __future__ import annotations

import json
import re
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BOT = Path(__file__).resolve().parent
STATE = BOT / "state.json"
COMMENTS_FILE = BOT / "comments.json"
LOG_FILE = BOT / "auto_log.json"
HISTORY_FILE = BOT / "posted_history.jsonl"
REPLIED_FILE = BOT / "replied_urls.json"
RETRY_FILE = BOT / "retry_queue.json"
PHOTO = BOT / "promo.jpg"
SHOTS = BOT / "shots"
SHOTS.mkdir(exist_ok=True)

GAP_MIN, GAP_MAX = 110.0, 135.0  # + ~85s post -> ~16-19/jam, ekstrem tetap <20 (target 15-20/jam, diatur 2026-10-13)
MAX_RETRIES = 2                  # attempts per URL via retry queue
MAX_PER_RUN = 4                  # replies per run (keeps one run ~12 min)
SESSION_FILE = BOT / "session.json"  # 24h window; bot stops when elapsed
RETRYABLE = {
    "type_failed", "submit_failed", "photo_preview_missing",
    "photo_lost_after_typing", "not_verified_on_page",
    "no_expand_button", "no_modal_composer",
    "no_top_reply_button",
}


# AFFILIATE VARIANT (clove/panah): media time-gate, 1h ON / 2h OFF (WIB).
# ON hours (WIB): 00, 03, 06, 09, 12, 15, 18, 21. Blooply instances do NOT use this.
# GENERIC-REACTION BAN (2026-11-01, Amad: no generic sentences like
# "Thanks for sharing"). KEEP IN SYNC: auto_comment.py + merge_comments.py
# in BOTH instances. A reaction is banned when its FIRST sentence, after
# stripping punctuation/emoji and lowercasing, EQUALS a banned phrase, or
# starts with one followed only by short fillers (no word >= 4 chars).
# A phrase followed by real content words is NOT banned (it carries detail).
GENERIC_BANNED = [
    "thanks for sharing",
    "topiknya menarik banget",
    "interesting post",
    "wah menarik juga pembahasan ini",
    "kontennya menarik",
    "setuju banget sama komentar tadi",
    "isi kontennya bikin gue mikir",
    "wah ini sesuai banget sama yang lagi gue bahas",
    "postingannya bikin guampang baca",
    "ini cocok banget buat diobrolin bareng teman-teman",
    "ini mah ga kebohongan",
    "seru ya diskusiannya",
]

def is_generic_reaction(text):
    t = (text or "").strip()
    if not t:
        return False
    first = re.split(r"[.!?\n]+", t, maxsplit=1)[0].strip().lower()
    s = re.sub(r"[^\w\s]", "", first, flags=re.UNICODE).strip()
    s = re.sub(r"\s+", " ", s)
    for b in GENERIC_BANNED:
        if s == b:
            return True
        if s.startswith(b + " "):
            rest = s[len(b):].strip()
            if not any(len(w) >= 4 for w in rest.split()):
                return True
            return False
    return False


def media_gate_on(now=None):
    t = now if now is not None else datetime.now(timezone.utc)
    wib_hour = (t.hour + 7) % 24
    return wib_hour % 3 == 0


# TOP-REPLY MODEL V2 (2026-10-31, perintah pemilik 14:48 WIB; menggantikan
# model v1 post-XOR-top_reply). Balasan ke POST UTAMA WAJIB SELALU untuk
# setiap item. Balasan ke BALASAN ATAS hanya TAMBAHAN (extra): bila post
# dirasa ramai (jumlah balasan >= ambang), bot JUGA membalas balasan atas
# yang tampil SAAT POSTING (guard dilonggarkan: tidak ada lagi pembatalan
# top_reply_changed; extra tidak pernah dibatalkan karena balasan atas
# berganti, melainkan fallback ke balasan atas saat itu). Bila balasan atas
# saat posting masuk kategori skip, extra di-skip SAJA, balasan utama tetap
# jalan. Targeting mechanism sama seperti v1 (urutan visual y, ikon balon
# SVG, fallback tombol ke-2 grup 4 tombol action bar).
TOP_REPLY_BUBBLE_PREFIX = "M12 3a9 9 0 0 0 0 18"


def load_top_reply_config():
    """Per-instance top-reply policy, dibaca FRESH tiap item saat posting
    (bukan hanya saat refill), jadi mengubah file ini berlaku tanpa restart.

    Keys: enabled (bool), mode ("main_plus_extra" atau "never"),
    busy_threshold (int, default 20 balasan), skip_extra_on_skip_category
    (bool, default True), extra_delay_min/max (detik, default 60/120).
    Kompatibel mundur: mode lama "auto"/"always" = extra aktif, "never" =
    extra nonaktif; key lama skip_top_reply_on_skip_category dipakai bila
    key baru tidak ada."""
    cfg = load_json(BOT / "top_reply_config.json", {})
    if not isinstance(cfg, dict):
        cfg = {}
    enabled = cfg.get("enabled", True)
    mode = cfg.get("mode", "main_plus_extra")
    if mode == "never":
        enabled = False
    skip_extra = cfg.get(
        "skip_extra_on_skip_category",
        cfg.get("skip_top_reply_on_skip_category", True),
    )
    try:
        threshold = int(cfg.get("busy_threshold", 20))
    except Exception:
        threshold = 20
    try:
        dmin = float(cfg.get("extra_delay_min", 60))
    except Exception:
        dmin = 60.0
    try:
        dmax = float(cfg.get("extra_delay_max", 120))
    except Exception:
        dmax = 120.0
    if dmax < dmin:
        dmax = dmin
    return {
        "enabled": enabled,
        "mode": "main_plus_extra" if enabled else "never",
        "busy_threshold": threshold,
        "skip_extra_on_skip_category": skip_extra,
        "extra_delay_min": dmin,
        "extra_delay_max": dmax,
    }


def item_key(item):
    """Composite dedup/replied key. Plain URL for post items, so old queue
    entries and old replied_urls.json entries keep matching exactly.
    Legacy top_reply items (model v1) map to the extra key."""
    u = item.get("url", "")
    return u + "#top_reply" if item.get("target") == "top_reply" else u


def extra_key(url):
    """Dedup key for the EXTRA reply of a post (model v2)."""
    return (url or "") + "#top_reply"


def norm_text(s):
    return " ".join((s or "").split())


_TOP_REPLY_ROW_JS = """
    const list = [...byHref.values()].sort((x, y) => x.y - y.y);
    const main = list.find(a => a.href.split('/').pop() === code);
    if (!main) return {has_replies: false, reason: 'main_not_found'};
    const after = list.filter(a => a.y > main.y);
    if (!after.length) return {has_replies: false, reason: 'no_replies'};
    const top = after[0];
    const btns = [...document.querySelectorAll('div[role=button], button')].map(el => {
        const r = el.getBoundingClientRect();
        if (r.width === 0 && r.height === 0) return null;
        const svg = el.querySelector('svg');
        if (!svg) return null;
        const path = [...svg.querySelectorAll('path')].map(p => p.getAttribute('d') || '').join('|');
        return {el, y: r.y + window.scrollY, x: r.x, path};
    }).filter(Boolean);
    // Groups below the reply anchor, top to bottom. The reply's own action
    // bar is the FIRST action bar below its anchor (nested replies render
    // below the bar, header icon groups above the text never contain the
    // bubble and never have 4 buttons). No upper bound: a quote card inside
    // the reply would otherwise cut the band short.
    const band = btns.filter(b => b.y > top.y)
        .sort((x, y) => (x.y - y.y) || (x.x - y.x));
    const groups = [];
    for (let i = 0; i < band.length;) {
        let j = i;
        while (j < band.length && Math.abs(band[j].y - band[i].y) <= 6) j++;
        groups.push(band.slice(i, j).sort((x, y) => x.x - y.x));
        i = j;
    }
    let row = [], method = null;
    const bubbleGroup = groups.find(g => g.some(b => b.path.indexOf('__BUBBLE__') === 0));
    const barGroup = groups.find(g => g.length === 4);
    if (bubbleGroup) { row = bubbleGroup; method = 'svg'; }
    else if (barGroup) { row = barGroup; method = 'position'; }
"""


def _top_reply_anchors_js():
    return """
    const anchors = [...document.querySelectorAll('a[href*="/post/"]')].map(a => {
        const r = a.getBoundingClientRect();
        return {href: a.getAttribute('href'), y: r.y + window.scrollY, el: a};
    }).filter(a => a.href && !a.href.endsWith('/media'));
    const byHref = new Map();
    for (const a of anchors) {
        if (!byHref.has(a.href) || a.y < byHref.get(a.href).y) byHref.set(a.href, a);
    }
"""


_TOP_REPLY_LOCATE_JS = ("""(code) => {
""" + _top_reply_anchors_js() + _TOP_REPLY_ROW_JS + """
    if (!row.length || !method) {
        const m0 = top.href.match(/^\\/@([^/]+)\\/post\\//);
        return {has_replies: true, top_reply_url: 'https://www.threads.com' + top.href,
                top_reply_author: m0 ? m0[1] : '', top_reply_text: '', reply_button: null};
    }
    let text = '';
    try {
        let el = top.el, best = null;
        for (let i = 0; i < 14 && el; i++) {
            el = el.parentElement;
            if (!el) break;
            const r = el.getBoundingClientRect();
            if (r.height > 120 && r.width > 300) {
                const t = (el.innerText || '').trim();
                if (t.length > 60) { best = el; break; }
            }
        }
        if (best) {
            const lines = (best.innerText || '').trim().split('\\n').map(s => s.trim()).filter(Boolean);
            const tEl = best.querySelector('time');
            const ageTxt = tEl ? (tEl.innerText || '').trim() : '';
            const body = lines.filter((s, i) => i > 0 && s !== ageTxt && !/^[\\d.,]+[KM]?$/.test(s));
            text = body.join(' ').slice(0, 600);
        }
    } catch (e) {}
    const m = top.href.match(/^\\/@([^/]+)\\/post\\//);
    return {has_replies: true, top_reply_url: 'https://www.threads.com' + top.href,
            top_reply_author: m ? m[1] : '', top_reply_text: text, reply_button: method};
}""").replace("__BUBBLE__", TOP_REPLY_BUBBLE_PREFIX)


_TOP_REPLY_CLICK_JS = ("""(topHref) => {
""" + _top_reply_anchors_js() + """
    const list = [...byHref.values()].sort((x, y) => x.y - y.y);
    // topHref may be a full URL (as stored in items) or a raw href path;
    // anchors carry raw href paths, so match both forms.
    const top = list.find(a => a.href === topHref
        || ('https://www.threads.com' + a.href) === topHref);
    if (!top) return false;
""" + _TOP_REPLY_ROW_JS.replace("const top = after[0];", "/* top already bound */").replace(
    "const list = [...byHref.values()].sort((x, y) => x.y - y.y);",
    "/* list already bound */").replace(
    "const main = list.find(a => a.href.split('/').pop() === code);",
    "/* main not needed */").replace(
    "if (!main) return {has_replies: false, reason: 'main_not_found'};",
    "").replace(
    "const after = list.filter(a => a.y > main.y);",
    "").replace(
    "if (!after.length) return {has_replies: false, reason: 'no_replies'};",
    "") + """
    if (!row.length || !method) return false;
    const btn = method === 'svg'
        ? row.find(b => b.path.indexOf('__BUBBLE__') === 0)
        : row[1];
    if (!btn || !btn.el) return false;
    btn.el.click();
    return method;
}""").replace("__BUBBLE__", TOP_REPLY_BUBBLE_PREFIX)


def find_top_reply_info(page, url):
    """Read-only: identify the current top reply of a thread page.

    Returns {has_replies, top_reply_url, top_reply_author, top_reply_text,
    reply_button} or {has_replies: False, reason}. Never clicks, never types.
    """
    empty = {"has_replies": False, "reason": "unknown"}
    try:
        page.evaluate("() => window.scrollTo(0, 0)")
        page.wait_for_timeout(700)
    except Exception:
        pass
    for _ in range(6):
        try:
            page.evaluate(
                """() => {
                    const rx = /show replies|view more replies|view all replies|lihat balasan|balasan lainnya/i;
                    const btns = [...document.querySelectorAll('div[role=button],button,span[role=button]')]
                        .filter(b => rx.test((b.innerText || '').trim()));
                    btns.slice(0, 6).forEach(b => { try { b.click(); } catch (e) {} });
                }"""
            )
        except Exception:
            pass
        try:
            page.mouse.wheel(0, 1200)
        except Exception:
            pass
        page.wait_for_timeout(420)
    code = (url or "").rstrip("/").split("/")[-1]
    try:
        info = page.evaluate(_TOP_REPLY_LOCATE_JS, code)
    except Exception:
        return dict(empty)
    if not isinstance(info, dict):
        return dict(empty)
    return info


def click_top_reply_button(page, top_href):
    """Click the Reply button belonging to the given top-reply permalink.

    Returns 'svg' or 'position' on success, False when the button cannot be
    found. The caller must NOT fall back to the main post composer on False:
    posting to the wrong place is worse than failing the item.
    """
    try:
        return page.evaluate(_TOP_REPLY_CLICK_JS, top_href)
    except Exception:
        return False


# Poster-side skip matcher for the EXTRA reply (model v2). Conservative
# first pass: only clear signals. Refill remains the primary filter; this
# is the safety net at posting time, when the top reply may have changed.
# Returns a category name or None. Matching is case-insensitive substring
# on lowered text, except the \b-marked words which use word boundaries.
import re as _re

_SKIP_RULES = [
    ("duka", ["turut berduka", "duka cita", "innalillahi", "rest in peace",
              "meninggal", "wafat", "berpulang", "turut berbelasungkawa"]),
    ("romance_spam", ["cari pacar", "cari jodoh", "open bo"]),
    ("income_bait", ["lunasin utang", "modal kecil untung besar", "gas malem",
                     "modal berapapun", "cepat kaya"]),
    ("flame_war", ["bangsat", "tolol", "goblok"]),
    ("politik_ekstrem", ["rezim", "buzzer", "protester", "boycoot",
                         "state corruption", "forest fires",
                         "indonesians first", "malaysian first", "windah"]),
    ("jasa_edit", ["open jasa edit", "jasa edit video", "pricelist",
                   "fee by dm"]),
    ("loker_non_editor", ["backend developer", "frontend developer",
                          "quality assurance", "technical writer",
                          "lowongan"]),
    ("jualan", ["mac mini", "brand new in box"]),
]

_SKIP_WORD_RULES = [
    ("duka", r"\brip\b"),
    ("politik_ekstrem", r"\bhack\b"),
]


def skip_category_of(text):
    """Category name when text matches a skip category, else None."""
    t = (text or "").lower()
    for cat, kws in _SKIP_RULES:
        for kw in kws:
            if kw in t:
                return cat
    for cat, pat in _SKIP_WORD_RULES:
        if _re.search(pat, t):
            return cat
    return None


def count_replies(page, url):
    """Read-only: count distinct reply permalinks in the thread.

    Threads virtualizes long threads: only a window of replies is mounted
    at any time, so a single snapshot undercounts badly (dry run
    2026-10-31: one snapshot saw 4-11 replies on an active thread).
    This function therefore ACCUMULATES distinct hrefs across scroll
    steps: after each wheel step it collects the mounted reply anchors
    below the main post anchor (excluding /media) and adds them to a set.
    Nested replies to replies are included: the number measures how busy
    the discussion is, not just top-level replies. Still a lower bound
    (replies never scrolled into view are missed), but far closer to the
    true count than a single snapshot. Returns 0 when uncountable."""
    code = (url or "").rstrip("/").split("/")[-1]
    js = """(code) => {
        const anchors = [...document.querySelectorAll('a[href*="/post/"]')]
            .map(a => ({href: a.getAttribute('href'),
                        y: a.getBoundingClientRect().y + window.scrollY}))
            .filter(a => a.href && !a.href.endsWith('/media'));
        const byHref = new Map();
        for (const a of anchors) {
            if (!byHref.has(a.href) || a.y < byHref.get(a.href).y) byHref.set(a.href, a);
        }
        const list = [...byHref.values()].sort((x, y) => x.y - y.y);
        const main = list.find(a => a.href.split('/').pop() === code);
        if (!main) return [];
        return list.filter(a => a.y > main.y).map(a => a.href);
    }"""
    seen = set()
    try:
        page.evaluate("() => window.scrollTo(0, 0)")
        page.wait_for_timeout(700)
    except Exception:
        pass
    for _ in range(16):
        try:
            hrefs = page.evaluate(js, code)
            if isinstance(hrefs, list):
                seen.update(hrefs)
        except Exception:
            pass
        try:
            page.mouse.wheel(0, 1500)
        except Exception:
            pass
        page.wait_for_timeout(400)
    try:
        hrefs = page.evaluate(js, code)
        if isinstance(hrefs, list):
            seen.update(hrefs)
    except Exception:
        pass
    return len(seen)


def author_replied_24h(author):
    """True when author (case-insensitive) has a successful post in
    posted_history.jsonl within the last 24h. Used for the EXTRA reply:
    the top-reply author at posting time may differ from refill time, so
    the 24h author filter is re-checked live for the extra target."""
    if not author or not HISTORY_FILE.exists():
        return False
    cutoff = datetime.now(timezone.utc).timestamp() - 86400
    a = author.strip().lower()
    try:
        for line in HISTORY_FILE.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if not r.get("ok"):
                continue
            try:
                ts = datetime.fromisoformat(r["ts"]).timestamp()
            except Exception:
                continue
            if ts >= cutoff and (r.get("author") or "").strip().lower() == a:
                return True
    except Exception:
        return False
    return False


def page_is_deleted_stub(page):
    """True for the short 'Post not available' stub of a deleted post."""
    try:
        return bool(page.evaluate(
            "() => {"
            "  const t = document.body.innerText || '';"
            "  return /post not available|post unavailable|post tidak tersedia/i.test(t)"
            "    && t.length < 400;"
            "}"
        ))
    except Exception:
        return False


def load_json(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return default


def save_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1))


def count_24h():
    cutoff = datetime.now(timezone.utc).timestamp() - 86400
    n = 0
    if HISTORY_FILE.exists():
        for line in HISTORY_FILE.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                if r.get("ok") and datetime.fromisoformat(r["ts"]).timestamp() >= cutoff:
                    n += 1
            except Exception:
                continue
    return n


def append_history(rec):
    slim = {k: rec.get(k) for k in ("ts", "url", "author", "lang", "ok", "skipped", "error")}
    slim["comment"] = (rec.get("comment") or "")[:200]
    # photo diagnostics — tanpa ini kita buta soal status media (bug 2026-10-04:
    # reply terkirim tanpa foto berhari-hari dan tidak ada jejak di history).
    for k in ("photo_attached", "photo_skipped", "photo_lost_after_typing",
              "photo_img_count", "photo_error"):
        if rec.get(k) is not None:
            slim[k] = rec.get(k)
    with HISTORY_FILE.open("a") as f:
        f.write(json.dumps(slim, ensure_ascii=False) + "\n")


def mark_replied(url):
    urls = load_json(REPLIED_FILE, [])
    if url not in urls:
        urls.append(url)
        save_json(REPLIED_FILE, urls)


def detect_lang(text: str) -> str:
    """Rough language detection: 'id' if Indonesian markers dominate, else 'en'."""
    import re
    t = (text or "").lower()
    id_words = [
        "yang", "aku", "kamu", "gue", "gw", "banget", "untuk", "bisa", "gimana",
        "udah", "biar", "bikin", "sih", "nih", "kalo", "kalau", "juga", "dengan",
        "dari", "ini", "itu", "tapi", "pakai", "cara", "orang", "konten", "video",
        "bisnis", "kerja", "masih", "belum", "jadi", "kita", "kalian", "buat",
        "gak", "nggak", "ga", "aja", "dong", "kok", "bgt", "wkwk", "nya",
    ]
    score = sum(1 for w in id_words if re.search(r"\b" + w + r"\b", t))
    return "id" if score >= 2 else "en"


def build_queue():
    """Queue entries under model v2. Each entry carries a main comment and
    an optional extra_comment; per-part done flags come from replied_urls
    (main key = plain URL, extra key = URL + "#top_reply").

    A retry entry blocks its URL from the comments.json path (dead or live,
    as in v1) so drafts cannot resurrect with fails reset. Legacy v1 items
    with target=top_reply (extra text stored as comment) are converted to
    extra-only entries. Entries survive when at least one part is fresh."""
    replied = set(load_json(REPLIED_FILE, []))
    retry = [r for r in load_json(RETRY_FILE, []) if r.get("url")]
    retry_items, items, seen_main, seen_extra = [], [], set(), set()
    for r in retry:
        url = r["url"]
        if r.get("target") == "top_reply" and not r.get("extra_comment"):
            r = dict(r, extra_comment=r.get("comment", ""), comment="")
        main_key, ex_key = url, extra_key(url)
        if r.get("dead") or r.get("fails", 0) >= MAX_RETRIES:
            seen_main.add(main_key)
            seen_extra.add(ex_key)
            continue
        main_done = main_key in replied
        extra_done = (ex_key in replied) or not r.get("extra_comment")
        if main_done and extra_done:
            seen_main.add(main_key)
            seen_extra.add(ex_key)
            continue
        seen_main.add(main_key)
        seen_extra.add(ex_key)
        retry_items.append({
            "url": url, "author": r.get("author", ""), "comment": r.get("comment", ""),
            "extra_comment": r.get("extra_comment", ""), "top_reply": r.get("top_reply"),
            "lang": r.get("lang", ""), "fails": r.get("fails", 0),
            "media_path": r.get("media_path", ""),
            "main_done": main_done, "extra_done": extra_done,
        })
    for c in load_json(COMMENTS_FILE, []):
        url = c.get("url")
        if not url:
            continue
        if c.get("target") == "top_reply" and not c.get("extra_comment"):
            c = dict(c, extra_comment=c.get("comment", ""), comment="")
        main_key, ex_key = url, extra_key(url)
        main_fresh = bool(c.get("comment")) and main_key not in replied and main_key not in seen_main
        extra_fresh = bool(c.get("extra_comment")) and ex_key not in replied and ex_key not in seen_extra
        if not main_fresh and not extra_fresh:
            continue
        if main_fresh:
            seen_main.add(main_key)
        if extra_fresh:
            seen_extra.add(ex_key)
        items.append({
            "url": url, "author": c.get("author", ""),
            "comment": c.get("comment", "") if main_fresh else "",
            "extra_comment": c.get("extra_comment", "") if extra_fresh else "",
            "top_reply": c.get("top_reply"),
            "lang": c.get("lang") or detect_lang(c.get("comment", "") or c.get("extra_comment", "")),
            "fails": 0, "media_path": c.get("media_path", ""),
            "main_done": not main_fresh, "extra_done": not extra_fresh,
        })
    # Prioritas: post Indonesia dulu (user rule), lalu EN. Retry items tetap
    # di depan (sudah pernah dicoba).
    id_items = [x for x in items if x.get("lang") == "id"]
    en_items = [x for x in items if x.get("lang") != "id"]
    ordered = retry_items + id_items + en_items
    return ordered[:MAX_PER_RUN]


def shot(page, name):
    try:
        page.screenshot(path=str(SHOTS / f"{name}.png"))
    except Exception:
        pass


def find_text_state(page, snippet, max_screens=30, expand=True):
    """Deep-scan the thread for `snippet`; return occurrence counts.

    Scrolls top->bottom in small steps, expanding collapsed replies ("Show
    replies"), and normalizes whitespace before comparing. Fixes false-negative
    verification on long threads (2026-09-29 bug: the fresh reply sat below the
    fold / was lazily rendered; viewport-only checks missed it and retries
    posted duplicate replies).
    Returns {n_body, n_comp, found_outside}:
      n_body        = snippet occurrences in body.innerText (normalized)
      n_comp        = occurrences inside contenteditable composers
      found_outside = a copy exists outside any composer draft
    """
    norm = " ".join((snippet or "").split())
    empty = {"n_body": 0, "n_comp": 0, "found_outside": False}
    if not norm:
        return empty

    def state():
        try:
            return page.evaluate(
                """(t) => {
                    const norm = s => (s || '').replace(/\\s+/g, ' ').trim();
                    const count = (hay, needle) => {
                        let n = 0, i = 0;
                        while ((i = hay.indexOf(needle, i)) !== -1) { n++; i += needle.length; }
                        return n;
                    };
                    const body = norm(document.body.innerText);
                    const comp = norm([...document.querySelectorAll("div[contenteditable='true']")]
                        .map(e => e.innerText).join(' '));
                    const n_body = count(body, t);
                    const n_comp = count(comp, t);
                    return {n_body, n_comp, found_outside: (n_body - n_comp) > 0};
                }""",
                norm,
            )
        except Exception:
            return dict(empty)

    try:
        page.evaluate("() => window.scrollTo(0, 0)")
        page.wait_for_timeout(700)
    except Exception:
        pass
    st = state()
    if st["found_outside"]:
        return st
    for i in range(max_screens):
        if expand and i % 3 == 0:
            try:
                page.evaluate(
                    """() => {
                        const rx = /show replies|view more replies|view all replies|lihat balasan|balasan lainnya/i;
                        const btns = [...document.querySelectorAll('div[role=button],button,span[role=button]')]
                            .filter(b => rx.test((b.innerText || '').trim()));
                        btns.slice(0, 6).forEach(b => { try { b.click(); } catch (e) {} });
                    }"""
                )
            except Exception:
                pass
        try:
            page.mouse.wheel(0, 1200)
        except Exception:
            pass
        page.wait_for_timeout(420)
        st = state()
        if st["found_outside"]:
            return st
    return state()


def pending_approval_gate(page):
    """True if the thread requires the author's approval for replies.

    Such threads show a "Pending author approval" hint; our reply stays
    invisible until the author approves it, so on-page verification can never
    pass and retrying only creates duplicate pending replies
    (x0tiago case, 2026-09-30)."""
    try:
        return bool(page.evaluate(
            """() => /pending author approval|menunggu persetujuan penulis/i
                     .test(document.body.innerText || '')"""
        ))
    except Exception:
        return False


def post_reply(ctx, page, url, text, idx, media_path=None, target="post", top_reply=None):
    rec = {"url": url, "ts": datetime.now(timezone.utc).isoformat(), "ok": False}
    page.goto(url, timeout=90000, wait_until="domcontentloaded")
    page.wait_for_timeout(5000)

    # GUARD 2026-10-08e (watchdog): post dihapus -> URL /post/ me-redirect ke
    # halaman PROFIL author. Di sana rantai "Expand composer" membuka composer
    # BUAT THREAD BARU -> retry berubah jadi post top-level yang salah sasaran.
    # Deteksi redirect dan tandai post_deleted (non-retryable).
    try:
        if "/post/" in url and "/post/" not in page.url:
            rec["error"] = "post_deleted"
            rec["landed"] = page.url[:200]
            shot(page, f"err_{idx}_deleted")
            return rec
    except Exception:
        pass

    # idempotency: sudah pernah reply? (juga menyembuhkan verifikasi gagal sebelumnya)
    # Deep scan (scroll + expand) — viewport-only check missed replies on long
    # threads, causing retries that posted duplicate replies (bug 2026-09-29).
    try:
        if find_text_state(page, text[:40], max_screens=24)["found_outside"]:
            rec["ok"] = True
            rec["skipped"] = "already_replied"
            return rec
    except Exception:
        pass

    # Approval-gate ("Pending author approval"): reply tidak terlihat sampai
    # disetujui penulis -> tidak bisa diverifikasi, dan retry hanya bikin
    # reply pending dobel (kasus @x0tiago 2026-09-30).
    if pending_approval_gate(page):
        rec["skipped"] = "pending_author_approval"
        rec["error"] = "pending_author_approval"
        return rec

    # Catat apakah tombol "Expand composer" sudah ada SEBELUM klik Reply —
    # varian A: inline composer + tombol Expand sudah ada sejak load.
    # varian B (watchdog 2026-10-08): tidak ada apa-apa saat load; klik Reply
    # hanya memunculkan sticky composer + tombol Expand yang baru muncul
    # setelahnya; modal asli baru terbuka setelah tombol Expand diklik.
    try:
        expand_before = bool(page.evaluate(
            """() => !!(document.querySelector('[aria-label="Expand composer"]') || document.querySelector('[aria-label="展开编辑框"]'))"""
        ))
    except Exception:
        expand_before = False

    # EXTRA resolution (model v2, guard DILONGGARKAN): the extra text is
    # written to survive a changed top reply, so we ALWAYS resolve the
    # CURRENT top reply at posting time and post under it. There is NO
    # top_reply_changed cancellation anymore: if the top reply changed
    # since refill, the extra falls back to the top reply visible NOW.
    # The caller (post_item) already checked busy + skip-category + author
    # filter; this block only resolves the live target and fails safe when
    # there is no reply at all. NEVER downgrade an extra to a main-post
    # reply: posting extra text to the main post would double the main
    # reply slot, so a disabled extra fails safe instead.
    _target = target or "post"
    _top = top_reply if isinstance(top_reply, dict) else None
    if _target == "top_reply":
        _cfg = load_top_reply_config()
        if not _cfg.get("enabled", True):
            rec["target"] = "top_reply"
            rec["error"] = "extra_disabled"
            return rec
        _info = find_top_reply_info(page, url)
        if not _info.get("has_replies") or not _info.get("top_reply_url"):
            rec["target"] = "top_reply"
            rec["error"] = "no_replies"
            shot(page, f"err_{idx}_noreplies")
            return rec
        _top = {"author": _info.get("top_reply_author", ""),
                "text": _info.get("top_reply_text", ""),
                "url": _info.get("top_reply_url")}
        rec["target"] = "top_reply"
        rec["top_reply_url"] = _top["url"]
        rec["top_reply_author"] = _top["author"]

    # 1) buka modal composer (multi-fallback: label bisa beda per versi UI/post)
    if _target == "top_reply":
        _clicked = click_top_reply_button(page, _top["url"])
        if not _clicked:
            if page_is_deleted_stub(page):
                rec["error"] = "post_deleted"
                rec["landed"] = page.url[:200]
                shot(page, f"err_{idx}_unavail")
                return rec
            rec["error"] = "no_top_reply_button"
            rec["target"] = "top_reply"
            shot(page, f"err_{idx}_topbtn")
            return rec
        rec["reply_button_via"] = _clicked
        opened = True
    else:
        rec["target"] = "post"
        opened = page.evaluate(
        """() => {
            const sels = [
                '[aria-label="Expand composer"]',
                '[aria-label="展开编辑框"]',
                '[aria-label="Reply"]',
                '[aria-label="Balas"]',
                'svg[aria-label="Reply"]',
                '[role="button"][aria-label*="composer" i]',
                '[role="button"][aria-label*="编辑框" i]',
                '[role="button"][aria-label*="reply" i]',
                '[role="button"][aria-label*="balas" i]',
            ];
            for (const s of sels) {
                const el = document.querySelector(s);
                if (el) { el.click(); return s; }
            }
            // last resort: find a button/svg whose text or label is Reply/Balas
            const cands = [...document.querySelectorAll('[role="button"], button, svg')];
            const hit = cands.find(e => {
                const t = (e.getAttribute('aria-label') || e.textContent || '').trim().toLowerCase();
                return t === 'reply' || t === 'balas' || t === 'expand composer' || t === '展开编辑框';
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
        }"""
    )
        if not opened:
            # GUARD 2026-10-08f (watchdog): varian "Post not available" - post
            # dihapus tanpa redirect (URL tetap /post/). Halaman stub hanya
            # berisi navigasi + placeholder "Post not available" (~200 char)
            # dan tanpa affordance reply sama sekali. Halaman LIVE yang
            # root-nya sudah dihapus (mis. osbuhh) memuat placeholder yang
            # sama tapi tetap panjang & punya affordance -> syarat len<400
            # membedakannya. Non-retryable: perlakukan seperti post_deleted
            # supaya tidak membakar 2 retry lalu jadi tombstone tanpa
            # skip_reason (alert watchdog @orcamel + @progressivepoliticsni
            # 2026-10-08).
            if page_is_deleted_stub(page):
                rec["error"] = "post_deleted"
                rec["landed"] = page.url[:200]
                shot(page, f"err_{idx}_unavail")
                return rec
            rec["error"] = "no_expand_button"
            shot(page, f"err_{idx}_expand")
            return rec
    page.wait_for_timeout(3200)

    # GUARD 2026-10-08: jangan pernah mengetik kalau modal composer tidak
    # benar-benar terbuka. Dulu saat modal gagal terbuka (no_dialog), teks
    # tetap diketik -> jatuh ke sticky composer halaman, Enter di sana ikut
    # mem-POST hanya baris pertama (promo hilang) dan sisanya jadi draft
    # (bug reply parsial: sueibrahimm/reenramlann/vanillaandbuttersbites).
    def modal_composer_ready():
        try:
            return bool(page.evaluate(
                "() => !!document.querySelector(\"div[role=dialog] div[contenteditable='true']\")"
            ))
        except Exception:
            return False

    click_expand_js = """() => {
        const el = document.querySelector('[aria-label="Expand composer"]') || document.querySelector('[aria-label="展开编辑框"]');
        if (!el) return false;
        el.click();
        return true;
    }"""

    if not modal_composer_ready() and not expand_before:
        # VARIAN B (watchdog 2026-10-08: sndikodrmwn/riyanaaseptianii/
        # asrytesa): klik Reply hanya memunculkan sticky composer + tombol
        # "Expand composer" yang baru ada SETELAH klik itu. Modal asli baru
        # terbuka setelah tombol Expand diklik. JANGAN pernah ketik ke sticky.
        for _ in range(4):  # maks ~6s
            clicked = page.evaluate(click_expand_js)
            if clicked:
                rec["modal_open_via"] = "expand_promote"
            page.wait_for_timeout(1500)
            if modal_composer_ready():
                break

    if not modal_composer_ready():
        for _ in range(30):  # modal kadang lambat render; tunggu s/d ~15s (watchdog 2026-10-08)
            page.wait_for_timeout(500)
            if modal_composer_ready():
                break

    if not modal_composer_ready():
        # Percobaan terakhir: klik tombol Expand sekali lagi (varian A yang
        # klik pertamanya tidak nyangkut).
        for _ in range(2):
            if not page.evaluate(click_expand_js):
                break
            rec["modal_open_via"] = "expand_promote_late"
            page.wait_for_timeout(1500)
            if modal_composer_ready():
                break

    if not modal_composer_ready():
        rec["error"] = "no_modal_composer"
        shot(page, f"err_{idx}_nomodal")
        return rec

    # 2) attach foto DULU (sebelum teks) — kalau attach setelah teks,
    #    composer re-render dan teks bisa terhapus (bug yang sudah kejadian).
    #    CIRCUIT BREAKER: server Threads membalas 400 "User restricted from
    #    uploading" (error_domain=integrity) saat akun kena restriksi upload.
    #    Setiap percobaan upload yang gagal = sinyal spam tambahan, jadi setelah
    #    2 kegagalan berturut kita berhenti mencoba foto selama 24 jam
    #    (flag file photo_disabled.json).
    import time as _time
    _photo_off_file = BOT / "photo_disabled.json"
    _photo_off = False
    if _photo_off_file.exists():
        try:
            _d = json.loads(_photo_off_file.read_text())
            if _time.time() < float(_d.get("until", 0)):
                _photo_off = True
                rec["photo_skipped"] = "restricted_cooldown"
        except Exception:
            pass
    # AFFILIATE media gate: 1h ON / 3h OFF (WIB). OFF -> no media at all.
    _media_file = None
    if media_path:
        try:
            _cand = Path(media_path)
            if _cand.exists():
                _media_file = _cand
        except Exception:
            _media_file = None
    if not media_gate_on():
        rec["photo_skipped"] = "media_window_off"
        _media_file = None
    elif _media_file is None:
        rec["photo_skipped"] = "no_media"
    if _media_file is not None and not _photo_off:
        # konfirmasi preview gambar ada — HANYA hitung blob: di dalam dialog
        # composer. Bug lama: menghitung semua img di halaman (termasuk gambar
        # post = false positive 20 gambar) -> reply terkirim tanpa foto berhari-hari.
        def composer_photo_count():
            try:
                return page.evaluate(
                    """() => {
                        const dlg = document.querySelector('div[role=dialog]');
                        if (!dlg) return 0;
                        return [...dlg.querySelectorAll('img')]
                            .filter(i => i.src && i.src.startsWith('blob:'))
                            .filter(i => { const r = i.getBoundingClientRect(); return r.width > 100 && r.height > 100; }).length;
                    }"""
                )
            except Exception:
                return 0

        def attach_photo():
            """Set file via PLAYWRIGHT NATIVE (set_input_files).
            BUG KRITIS (2026-10-04): CDP DOM.setFileInputFiles membuat page CRASH
            di Chromium 146 + CloakBrowser (bahkan di halaman lokal sederhana).
            Playwright native set_input_files terbukti BEKERJA. Jangan pakai CDP
            untuk upload file di environment ini."""
            for attempt in range(3):  # up to ~6s (jangan lama: tiap gagal = sinyal)
                try:
                    inp = page.locator("div[role=dialog] input[type=file]").first
                    if inp.count() == 0:
                        inp = page.locator("input[type=file]").first
                    inp.set_input_files(str(_media_file), timeout=6000)
                    return True
                except Exception as e:
                    rec["photo_error"] = repr(e)[:120]
                    page.wait_for_timeout(2000)
            return False

        img_count = 0
        for attempt in range(2):  # max 2 percobaan; lebih dari itu = spam signal
            if not attach_photo():
                break
            for _ in range(10):    # poll every 2s
                img_count = composer_photo_count()
                if img_count > 0:
                    break
                page.wait_for_timeout(2000)
            if img_count > 0:
                break
        rec["photo_attached"] = img_count > 0
        rec["photo_img_count"] = img_count
        if img_count == 0:
            # Foto gagal — posting teks saja, dan catat kegagalan berturut.
            rec["photo_skipped"] = True
            try:
                fails_file = BOT / "photo_fail_streak.json"
                streak = 0
                if fails_file.exists():
                    streak = int(json.loads(fails_file.read_text()).get("streak", 0))
                streak += 1
                fails_file.write_text(json.dumps({"streak": streak, "last": rec.get("ts")}))
                if streak >= 2:
                    # circuit breaker: matikan percobaan foto 24 jam
                    _photo_off_file.write_text(json.dumps({
                        "until": _time.time() + 86400,
                        "reason": "server rejected uploads (integrity restriction)",
                        "streak": streak,
                    }))
                    rec["photo_circuit_breaker"] = True
            except Exception:
                pass
        else:
            # sukses — reset streak
            try:
                (BOT / "photo_fail_streak.json").write_text(json.dumps({"streak": 0}))
            except Exception:
                pass

    # 3) isi teks SETELAH foto — pakai Playwright NATIVE (locator.click +
    #    keyboard.type). Ini satu-satunya metode yang terbukti reliable:
    #    execCommand('insertText') gagal senyap di modal, fill() menghapus \n.
    #    Enter sungguhan x2 menghasilkan baris kosong asli.
    #    CATATAN: saat foto terattach, preview bisa menutupi area teks ->
    #    click() kena pointer-events check. Fallback: JS focus + selection.
    typed = ""

    def focus_composer():
        """Return 'click' kalau native click berhasil, 'js' kalau fallback JS."""
        try:
            composer = page.locator("div[role=dialog] div[contenteditable='true']").last
            composer.click(timeout=8000)
            return "click"
        except Exception:
            # fallback: JS focus + collapse selection to end
            return page.evaluate(
                """() => {
                    const dlg = document.querySelector('div[role=dialog]');
                    if (!dlg) return 'no_dialog';
                    const ed = dlg.querySelector("div[contenteditable='true']");
                    if (!ed) return 'no_editable';
                    ed.focus();
                    const sel = window.getSelection();
                    const range = document.createRange();
                    range.selectNodeContents(ed);
                    range.collapse(false);
                    sel.removeAllRanges();
                    sel.addRange(range);
                    return document.activeElement === ed ? 'js' : 'js_failed';
                }"""
            )

    try:
        mode = focus_composer()
        rec["type_focus_mode"] = mode
        if mode in ("no_dialog", "no_editable", "js_failed"):
            # GUARD 2026-10-08: composer modal tidak fokus -> jangan mengetik
            # sama sekali (cegah reply parsial via sticky composer).
            rec["error"] = "no_modal_composer"
            shot(page, f"err_{idx}_nomodal")
            return rec
        page.wait_for_timeout(600)
        lines = text.split("\n\n")
        page.keyboard.type(lines[0], delay=20)
        page.wait_for_timeout(500)
        if len(lines) > 1:
            page.keyboard.press("Enter")
            page.wait_for_timeout(350)
            page.keyboard.press("Enter")
            page.wait_for_timeout(350)
            page.keyboard.type("\n\n".join(lines[1:]), delay=20)
        page.wait_for_timeout(1500)
        typed = page.evaluate(
            """() => {
                const eds = [...document.querySelectorAll("div[contenteditable='true']")]
                    .map(e => e.innerText).filter(Boolean);
                return eds.sort((a,b) => b.length - a.length)[0] || '';
            }"""
        )
    except Exception as e:
        rec["type_exc"] = repr(e)[:120]
    # Abort unless BOTH the start and the end of the comment are in the composer
    if text[:25] not in typed or text[-25:] not in typed:
        rec["error"] = "type_failed"
        rec["typed_preview"] = typed[:100]
        shot(page, f"err_{idx}_type")
        return rec
    rec["typed_ok"] = True
    # pastikan foto masih ada setelah mengetik — pakai selector composer yang
    # benar; kalau hilang (composer re-render), coba attach ulang 1x.
    if rec.get("photo_attached"):
        still = composer_photo_count()
        if still == 0:
            # re-attach sekali via Playwright native (CDP bikin crash)
            try:
                inp2 = page.locator("div[role=dialog] input[type=file]").first
                if inp2.count() == 0:
                    inp2 = page.locator("input[type=file]").first
                inp2.set_input_files(str(_media_file), timeout=8000)
                for _ in range(10):
                    page.wait_for_timeout(2000)
                    still = composer_photo_count()
                    if still > 0:
                        break
            except Exception:
                pass
        if still == 0:
            # Tetap posting teks saja, jangan buang reply.
            rec["photo_lost_after_typing"] = True
        else:
            rec["photo_still_ok"] = True

    # 4) jeda manusiawi lalu klik Post
    time.sleep(random.uniform(7, 11))
    posted = page.evaluate(
        """() => {
            const btns = [...document.querySelectorAll('div[role=button],button')]
                .filter(x => /^(Post|Posting|发布)$/i.test((x.innerText||'').trim()) || /^(Post|Posting|发布)$/i.test((x.getAttribute('aria-label')||'').trim()));
            const b = btns.find(x => x.getAttribute('aria-disabled') !== 'true');
            if (!b) return null;
            b.click();
            return 'clicked';
        }"""
    )
    rec["submit"] = posted
    if not posted:
        rec["error"] = "submit_failed"
        shot(page, f"err_{idx}_submit")
        return rec

    page.wait_for_timeout(12000)

    # Verify: deep-scan the whole thread (fresh reply can sit far below the
    # fold and lazily render) then look for the text OUTSIDE any composer draft.
    # FIX 2026-10-31: threads virtualizes long threads; 34 screens insufficient.
    # Scroll 80 steps + re-scan from top after reload to catch lazily-rendered reply.
    v = find_text_state(page, text[:40], max_screens=80)
    found = v["found_outside"]
    if not found:
        # Reload once: the thread may not render the fresh reply until refresh
        try:
            page.goto(url, timeout=90000, wait_until="domcontentloaded")
            page.wait_for_timeout(8000)
            v = find_text_state(page, text[:40], max_screens=80)
            found = v["found_outside"]
        except Exception:
            pass
    rec["ok"] = bool(found)
    rec["verified"] = bool(found)
    if not found:
        # Approval-gate: reply terkirim tapi belum terlihat (menunggu approval
        # penulis); retry = reply pending dobel. Bukan retryable.
        if pending_approval_gate(page):
            rec["skipped"] = "pending_author_approval"
            rec["error"] = "pending_author_approval"
        else:
            rec["error"] = "not_verified_on_page"
    # TOP-REPLY nesting check (DIAGNOSTIK ONLY, tidak pernah menggagalkan
    # post yang sudah terverifikasi di thread utama: kalau balasan sudah
    # tampil di thread, gagal di sini lalu retry justru berisiko dobel).
    # Balasan nested yang benar HARUS tampil sebagai balasan di halaman
    # permalink balasan atas itu sendiri; balasan langsung ke post utama
    # tidak akan tampil di sana.
    if _target == "top_reply" and found:
        try:
            page.goto(_top["url"], timeout=90000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            _nv = find_text_state(page, text[:40], max_screens=60)
            rec["nested_verified"] = bool(_nv["found_outside"])
        except Exception:
            rec["nested_verified"] = None
    shot(page, f"ok_{idx}" if found else f"unverified_{idx}")
    return rec


def decide_extra(item, current_top, reply_count, cfg, replied):
    """Gate for the EXTRA reply (model v2). Returns (do_extra, reason).

    current_top: dict from find_top_reply_info (or None). reply_count: int
    from count_replies at posting time. replied: set of replied keys.
    Order matters: cheap dedup/config checks first, then busy, then the
    live top-reply checks. A False here is a TERMINAL skip for the extra
    (the main reply still stands); only post errors are retried."""
    if not cfg.get("enabled", True):
        return False, "extra_disabled"
    if not item.get("extra_comment"):
        return False, "no_extra_text"
    if extra_key(item["url"]) in replied:
        return False, "extra_already_replied"
    if reply_count < cfg.get("busy_threshold", 20):
        return False, "not_busy"
    if not current_top or not current_top.get("has_replies") or not current_top.get("top_reply_url"):
        return False, "no_replies"
    if cfg.get("skip_extra_on_skip_category", True):
        cat = skip_category_of(current_top.get("top_reply_text", ""))
        if cat:
            return False, "skip_category:" + cat
    if author_replied_24h(current_top.get("top_reply_author", "")):
        return False, "author_24h"
    return True, "ok"


def post_extra_if_busy(ctx, page, item, idx, main_rec, cfg):
    """Attempt the EXTRA reply for one item. Returns None when the item
    carries no extra text, else a rec dict (ok / terminal skip / error).

    Gate failures are terminal skips for the extra (recorded with
    skipped=extra_<reason>, never retried). Only post errors in RETRYABLE
    come back as errors for the caller to requeue. Media: the extra never
    carries a photo when the main reply already attached one (no two photos
    in one thread); otherwise the same media gate applies as for main."""
    if not item.get("extra_comment"):
        return None
    url = item["url"]
    # Count FIRST: its scrolling renders lazy replies, which makes the
    # subsequent top-reply locate much more reliable (dry run 2026-10-31:
    # find-first returned no_replies while count-first found 11 replies on
    # the same thread, because replies had not rendered yet).
    try:
        n = count_replies(page, url)
    except Exception:
        n = 0
    try:
        info = find_top_reply_info(page, url)
    except Exception:
        info = {"has_replies": False}
    replied = set(load_json(REPLIED_FILE, []))
    do, reason = decide_extra(item, info, n, cfg, replied)
    rec = {"url": url, "ts": datetime.now(timezone.utc).isoformat(),
           "target": "top_reply",
           "top_reply_url": (info or {}).get("top_reply_url", ""),
           "top_reply_author": (info or {}).get("top_reply_author", ""),
           "reply_count": n, "extra_gate": reason}
    if not do:
        rec["ok"] = False
        rec["skipped"] = "extra_" + reason
        return rec
    # Human-like pause before the second reply in the same thread.
    try:
        time.sleep(random.uniform(cfg["extra_delay_min"], cfg["extra_delay_max"]))
    except Exception:
        pass
    media = None
    if not main_rec.get("photo_attached") and media_gate_on():
        media = item.get("media_path")
    erec = post_reply(ctx, page, url, item["extra_comment"], idx, media,
                      "top_reply", None)
    erec["comment"] = item["extra_comment"]
    erec["author"] = (info or {}).get("top_reply_author", "")
    erec["lang"] = item.get("lang", "")
    erec["target"] = "top_reply"
    erec["reply_count"] = n
    return erec


def post_item(ctx, page, item, idx):
    """Post one queue item under model v2: main reply ALWAYS, then an
    optional EXTRA reply to the current top reply when the thread is busy.

    Returns (main_rec, extra_rec_or_None). extra_rec is None when no extra
    was attempted (no extra text, or the main reply failed: never chase an
    extra on a broken thread). The extra text NEVER goes to the main post:
    it is posted only through the top-reply button, or not at all."""
    url = item["url"]
    # LINK-ALL defense (2026-11-01): never post a text without a link
    # when the item carries product_link (e.g. template drafts).
    _pl = item.get("product_link")
    if _pl and "http" not in (item.get("comment") or ""):
        item["comment"] = (item.get("comment") or "") + f" Link: {_pl}"
    if _pl and item.get("extra_comment") and "http" not in item["extra_comment"]:
        item["extra_comment"] = item["extra_comment"] + f" Link: {_pl}"
    # GENERIC-REACTION BAN (2026-11-01): never post a generic
    # reaction; terminal tombstone via non-retryable error.
    if not item.get("main_done") and is_generic_reaction(item.get("comment", "")):
        return {"url": url, "ts": datetime.now(timezone.utc).isoformat(),
                "ok": False, "error": "generic_banned",
                "comment": item.get("comment", ""), "author": item.get("author", ""),
                "lang": item.get("lang", "")}, None
    if item.get("main_done"):
        main_rec = {"url": url, "ts": datetime.now(timezone.utc).isoformat(),
                    "ok": True, "skipped": "already_replied"}
    else:
        main_rec = post_reply(ctx, page, url, item["comment"], idx,
                              item.get("media_path"), "post", None)
    main_rec["comment"] = item.get("comment", "")
    main_rec["author"] = item.get("author", "")
    main_rec["lang"] = item.get("lang", "")
    extra_rec = None
    if (main_rec.get("ok") and item.get("extra_comment")
            and is_generic_reaction(item["extra_comment"])):
        return main_rec, {"url": url, "ts": datetime.now(timezone.utc).isoformat(),
                "ok": False, "skipped": "extra_generic_banned",
                "comment": item.get("extra_comment", ""), "author": item.get("author", ""),
                "lang": item.get("lang", "")}
    if main_rec.get("ok"):
        cfg = load_top_reply_config()
        extra_rec = post_extra_if_busy(ctx, page, item, idx, main_rec, cfg)
    return main_rec, extra_rec


def advance_item(item, main_rec, extra_rec):
    """Per-part bookkeeping after post_item. Marks replied keys for resolved
    parts. Returns None when the item is fully resolved (caller pops it
    from retry_state), else a retry entry to store (live, or dead=True
    tombstone when retries are exhausted or the failure is terminal).
    Mirrors the v1 tombstone semantics so a dead entry keeps blocking the
    comments.json path from re-adding the item."""
    url = item["url"]
    main_ok = bool(main_rec.get("ok"))
    if main_ok:
        mark_replied(url)
    extra_ok = bool(extra_rec and extra_rec.get("ok"))
    extra_skip = bool(extra_rec and (
        (extra_rec.get("skipped") or "").startswith("extra_")
        or extra_rec.get("skipped") == "pending_author_approval"))
    if extra_ok or extra_skip:
        mark_replied(extra_key(url))
    if main_ok and (extra_rec is None or extra_ok or extra_skip):
        return None
    fails = item.get("fails", 0) + 1
    entry = {"url": url, "author": item.get("author", ""),
             "comment": item.get("comment", ""),
             "extra_comment": item.get("extra_comment", ""),
             "lang": item.get("lang", ""), "fails": fails,
             "media_path": item.get("media_path", ""),
             "top_reply": item.get("top_reply")}
    if main_rec.get("skipped") == "pending_author_approval":
        entry["skip_reason"] = "pending_author_approval"
    if main_rec.get("error") == "post_deleted":
        entry["skip_reason"] = "post_deleted"
    retryable = False
    if not main_ok and main_rec.get("error") in RETRYABLE:
        retryable = True
    if (extra_rec and not extra_ok and not extra_skip
            and extra_rec.get("error") in RETRYABLE):
        retryable = True
    if retryable and fails < MAX_RETRIES:
        return entry
    entry["dead"] = True
    return entry


def main() -> int:
    if not STATE.exists():
        print("NO_SESSION")
        return 2

    # File lock: cegah dua instance jalan bersamaan (cron overlap).
    import fcntl
    lock_path = BOT / ".auto_comment.lock"
    lock_fh = lock_path.open("w")
    try:
        fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("ALREADY_RUNNING")
        return 4

    # Sesi: unlimited (duration_hours None) atau berbatas jam. Tanpa sesi aktif
    # -> tunggu perintah user.
    sess = load_json(SESSION_FILE, None)
    if not sess or not sess.get("started_at"):
        print("SESSION_MISSING: tidak ada sesi aktif; tunggu perintah user")
        return 5
    try:
        started = datetime.fromisoformat(sess["started_at"])
        elapsed_h = (datetime.now(timezone.utc) - started).total_seconds() / 3600.0
        dur = sess.get("duration_hours")
        if dur is not None and elapsed_h >= float(dur):
            print(f"SESSION_EXPIRED elapsed={elapsed_h:.1f}h duration={float(dur):g}h")
            return 5
    except Exception:
        pass

    queue = build_queue()
    if not queue:
        print("NO_COMMENTS")
        return 0

    from cloakbrowser import launch

    browser = launch(headless=True, humanize=True, args=["--fingerprint=71529"])
    results = []
    retry_state = {r["url"]: r for r in load_json(RETRY_FILE, []) if r.get("url")}
    consec_fail = 0
    try:
        ctx = browser.new_context(storage_state=str(STATE))
        page = ctx.new_page()
        total = len(queue)
        for i, item in enumerate(queue):
            print(f"[{i+1}/{total}] {item['url']} extra={'ya' if item.get('extra_comment') else 'tidak'}", flush=True)
            try:
                main_rec, extra_rec = post_item(ctx, page, item, i)
            except Exception as e:
                main_rec = {"url": item["url"], "ts": datetime.now(timezone.utc).isoformat(),
                            "ok": False, "error": f"exc:{type(e).__name__}"}
                extra_rec = None
                print(f"   -> EXCEPTION: {type(e).__name__}: {e}", flush=True)
            for rec in (main_rec, extra_rec):
                if rec is None:
                    continue
                results.append(rec)
                save_json(LOG_FILE, results)
                append_history(rec)
            entry = advance_item(item, main_rec, extra_rec)
            if entry is None:
                retry_state.pop(item["url"], None)
                consec_fail = 0
                print(f"   -> OK main + extra={extra_rec.get('ok') if extra_rec else 'tidak ada'}", flush=True)
            else:
                if main_rec.get("skipped") == "pending_author_approval":
                    # Author-gated thread: not a real failure, do not count
                    # toward the consecutive-failure stop.
                    print("   -> SKIP: pending_author_approval (author-gated)", flush=True)
                else:
                    consec_fail += 1
                    print(f"   -> FAIL main={main_rec.get('error')} extra={extra_rec.get('error') if extra_rec else 'tidak ada'}", flush=True)
                retry_state[item["url"]] = entry
            save_json(RETRY_FILE, list(retry_state.values()))

            if consec_fail >= 3:
                print("STOP: 3 consecutive failures", flush=True)
                break
            if i < total - 1:
                wait = random.uniform(GAP_MIN, GAP_MAX)
                print(f"   waiting {wait:.0f}s...", flush=True)
                time.sleep(wait)
    finally:
        try:
            browser.close()
        except Exception:
            pass

    ok_n = sum(1 for r in results if r.get("ok"))
    fail_n = len(results) - ok_n
    print(f"SUMMARY ok={ok_n} fail={fail_n} retry={len(retry_state)} used24h={count_24h()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
