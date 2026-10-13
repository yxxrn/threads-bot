#!/usr/bin/env python3
"""Build a ready-to-draft pool from the ARCHIVE of previously found/fetched posts.

This is the fast path for refill: instead of scraping Threads again (5-10 min),
aggregate candidates already collected in found_posts*.json and
post_texts*.json — many include FULL text (og + domText) — filter them
(language, already-replied, queue, retry), and write pool_ready.json.

Output: pool_ready.json — list of {url, author, lang, text, source}
Prints: POOL: N ready (ID: x, EN: y, other: z)
"""
from __future__ import annotations

import glob
import json
import re
from pathlib import Path

BOT = Path(__file__).resolve().parent


def load(path, default):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return default


ID_WORDS = [
    "yang", "aku", "kamu", "gue", "gw", "banget", "untuk", "bisa", "gimana",
    "udah", "biar", "bikin", "sih", "nih", "kalo", "kalau", "juga", "dengan",
    "dari", "ini", "itu", "tapi", "pakai", "cara", "orang", "konten",
    "bisnis", "kerja", "masih", "belum", "jadi", "kita", "kalian", "buat",
    "gak", "nggak", "ga", "aja", "dong", "kok", "bgt", "wkwk", "nya", "saya",
    "anda", "mereka", "tidak", "sudah", "akan", "ingin", "mau", "lebih",
    "sama", "banyak", "gitu", "gini", "emang", "memang", "sangat", "sekali",
    "harus", "punya", "suka", "lihat", "tau", "tahu", "deh", "yah", "lah",
    "kan", "bang", "kak", "mas", "bro", "min", "gan", "guys", "uang", "jualan",
    "produk", "pelanggan", "usaha", "modal", "untung", "omzet", "promosi",
]
EN_WORDS = [
    "the", "and", "you", "for", "with", "this", "that", "have", "just", "your",
    "are", "how", "what", "when", "why", "can", "will", "not", "but", "from",
    "they", "been", "more", "some", "like", "get", "make", "still", "new",
]
# Vietnamese junk markers (their diacritics + common words) — the wide-keyword
# search pulls Vietnamese posts; drop them.
VN_WORDS = ["không", "người", "mình", "được", "như", "của", "với", "cho", "này", "thì", "đã", "có"]
KO_WORDS = ["입니다", "합니다", "있습니다", "그리고", "하는", "에서"]


def detect_lang(text: str) -> str:
    t = (text or "").lower()
    if any(re.search(r"(?<![^\W\d_])" + re.escape(w) + r"(?![^\W\d_])", t) for w in VN_WORDS):
        return "other"  # word-boundary: "chocolate"/"choice" must not trip the VN filter
    if any(w in t for w in KO_WORDS):
        return "other"
    # CJK / Thai / Arabic scripts -> other
    if re.search(r"[\u4e00-\u9fff\u3040-\u30ff\u0e00-\u0e7f\u0600-\u06ff]", t):
        return "other"
    id_score = sum(1 for w in ID_WORDS if re.search(r"\b" + re.escape(w) + r"\b", t))
    en_score = sum(1 for w in EN_WORDS if re.search(r"\b" + re.escape(w) + r"\b", t))
    # any ID marker wins if it beats EN (archives have 379 ID posts this way)
    if id_score >= 1 and id_score >= en_score:
        return "id"
    if en_score >= 1:
        return "en"
    return "other"


def best_text(rec: dict) -> str:
    """Prefer full fetched text, fall back to the search preview."""
    full = rec.get("full") or {}
    parts = []
    if isinstance(full, dict):
        og = (full.get("og") or "").strip()
        dom = (full.get("domText") or "").strip()
        if og:
            parts.append(og)
        if dom and dom not in og:
            parts.append(dom)
    t = rec.get("text") or ""
    if parts:
        t = " | ".join(parts)
    return t.strip()


def main() -> int:
    replied = set(load(BOT / "replied_urls.json", []))
    queue = {c.get("url") for c in load(BOT / "comments.json", []) if c.get("url")}
    retry = {r.get("url") for r in load(BOT / "retry_queue.json", []) if isinstance(r, dict)}
    history = set()
    hf = BOT / "posted_history.jsonl"
    if hf.exists():
        for line in hf.read_text().splitlines():
            try:
                history.add(json.loads(line).get("url"))
            except Exception:
                pass
    excluded = replied | queue | retry | history
    excluded = {str(u).replace("https://www.threads.com/", "https://threads.com/").replace("https://threads.net/", "https://threads.com/").rstrip("/") for u in excluded if u}

    pool = {}
    seen_texts = set()
    files = sorted(glob.glob(str(BOT / "found_posts*.json")) + glob.glob(str(BOT / "post_texts*.json")))
    for f in files:
        data = load(f, [])
        if not isinstance(data, list):
            continue
        for rec in data:
            if not isinstance(rec, dict):
                continue
            url = rec.get("url")
            _m = re.search(r"threads[.]com/@([^/]+)/post/", url or "")
            if not _m or not _m.group(1):
                continue
            _au = (rec.get("author") or "")
            _au = _au.lower()
            if _au and _au not in url.lower():
                continue
            url_n = str(url).replace("https://www.threads.com/", "https://threads.com/").replace("https://threads.net/", "https://threads.com/").rstrip("/")
            if not url or url_n in excluded or url in pool:
                continue
            text = best_text(rec)
            if len(text) < 50:
                continue  # too thin to draft a genuine reply
            # dedupe by content: the same post shows up under several quoted URLs
            norm = re.sub(r"\s+", " ", text.strip().lower())[:100]
            if norm in seen_texts:
                continue
            lang = detect_lang(text)
            if lang == "other":
                continue
            seen_texts.add(norm)
            pool[url] = {
                "url": url,
                "author": rec.get("author") or "",
                "lang": lang,
                "text": text[:1500],
                "source": Path(f).name,
            }

    items = sorted(pool.values(), key=lambda x: (x["lang"] != "id", x["author"]))
    (BOT / "pool_ready.json").write_text(json.dumps(items, ensure_ascii=False, indent=1))
    idn = sum(1 for x in items if x["lang"] == "id")
    enn = sum(1 for x in items if x["lang"] == "en")
    print(f"POOL: {len(items)} ready (ID: {idn}, EN: {enn})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
