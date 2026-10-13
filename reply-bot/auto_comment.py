#!/usr/bin/env python3
"""Full-auto reply pipeline v3 (continuous mode).

Queue (processed in order, deduped by URL):
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

GAP_MIN, GAP_MAX = 45.0, 75.0    # 0.75-1.25 min gap -> ~2.5-2.8 min per reply cycle (target >=20/jam)
MAX_RETRIES = 2                  # attempts per URL via retry queue
MAX_PER_RUN = 4                  # replies per run (keeps one run ~12 min)
SESSION_FILE = BOT / "session.json"  # 24h window; bot stops when elapsed
RETRYABLE = {
    "type_failed", "submit_failed", "photo_preview_missing",
    "photo_lost_after_typing", "not_verified_on_page",
    "no_expand_button", "no_modal_composer",
}


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
    replied = set(load_json(REPLIED_FILE, []))
    retry = [r for r in load_json(RETRY_FILE, []) if r.get("url")]
    retry_items, items, seen = [], [], set()
    for r in retry:
        if r["url"] in seen:
            continue
        # Any url present in retry_queue blocks the comments.json path below
        # (dead/exhausted included) — otherwise the draft gets re-added with
        # fails reset to 0 and retried forever (retry-loop bug 2026-09-29).
        seen.add(r["url"])
        if r.get("dead") or r.get("fails", 0) >= MAX_RETRIES:
            continue
        retry_items.append({
            "url": r["url"], "author": r.get("author", ""), "comment": r.get("comment", ""),
            "lang": r.get("lang", ""), "fails": r.get("fails", 0),
        })
    for c in load_json(COMMENTS_FILE, []):
        if not c.get("url") or not c.get("comment") or c["url"] in seen:
            continue
        # Skip URLs already successfully replied to (they stay in comments.json
        # as a draft archive; without this the queue would pick them forever).
        if c["url"] in replied:
            continue
        seen.add(c["url"])
        items.append({
            "url": c["url"], "author": c.get("author", ""), "comment": c["comment"],
            "lang": c.get("lang") or detect_lang(c.get("comment", "")), "fails": 0,
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


def post_reply(ctx, page, url, text, idx):
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
            """() => !!document.querySelector('[aria-label="Expand composer"]')"""
        ))
    except Exception:
        expand_before = False

    # 1) buka modal composer (multi-fallback: label bisa beda per versi UI/post)
    opened = page.evaluate(
        """() => {
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
            // last resort: find a button/svg whose text or label is Reply/Balas
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
        }"""
    )
    if not opened:
        # GUARD 2026-10-08f (watchdog): varian "Post not available" - post
        # dihapus tanpa redirect (URL tetap /post/). Halaman stub hanya berisi
        # navigasi + placeholder "Post not available" (~200 char) dan tanpa
        # affordance reply sama sekali. Halaman LIVE yang root-nya sudah
        # dihapus (mis. osbuhh) memuat placeholder yang sama tapi tetap
        # panjang & punya affordance -> syarat len<400 membedakannya.
        # Non-retryable: perlakukan seperti post_deleted supaya tidak
        # membakar 2 retry lalu jadi tombstone tanpa skip_reason
        # (alert watchdog @orcamel + @progressivepoliticsni 2026-10-08).
        try:
            _unavail = bool(page.evaluate(
                "() => {"
                "  const t = document.body.innerText || '';"
                "  return /post not available|post unavailable|post tidak tersedia/i.test(t)"
                "    && t.length < 400;"
                "}"
            ))
        except Exception:
            _unavail = False
        if _unavail:
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
        const el = document.querySelector('[aria-label="Expand composer"]');
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
    if PHOTO.exists() and not _photo_off:
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
                    inp.set_input_files(str(PHOTO), timeout=6000)
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
                inp2.set_input_files(str(PHOTO), timeout=8000)
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
                .filter(x => /^(Post|Posting)$/i.test((x.innerText||'').trim()));
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

    page.wait_for_timeout(8000)

    # Verify: deep-scan the whole thread (fresh reply can sit far below the
    # fold and lazily render) then look for the text OUTSIDE any composer draft.
    v = find_text_state(page, text[:40], max_screens=34)
    found = v["found_outside"]
    if not found:
        # Reload once: the thread may not render the fresh reply until refresh
        try:
            page.goto(url, timeout=90000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            v = find_text_state(page, text[:40], max_screens=40)
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
    shot(page, f"ok_{idx}" if found else f"unverified_{idx}")
    return rec


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
            print(f"[{i+1}/{total}] {item['url']}", flush=True)
            rec = post_reply(ctx, page, item["url"], item["comment"], i)
            rec["comment"] = item["comment"]
            rec["author"] = item.get("author", "")
            rec["lang"] = item.get("lang", "")
            results.append(rec)
            save_json(LOG_FILE, results)
            append_history(rec)

            if rec.get("ok"):
                consec_fail = 0
                mark_replied(item["url"])
                retry_state.pop(item["url"], None)
                print("   -> OK", flush=True)
            else:
                err = rec.get("error", "?")
                if rec.get("skipped") == "pending_author_approval":
                    # Author-gated thread: not a real failure, do not count
                    # toward the consecutive-failure stop.
                    print("   -> SKIP: pending_author_approval (author-gated)", flush=True)
                else:
                    consec_fail += 1
                    print(f"   -> FAIL: {err}", flush=True)
                fails = item.get("fails", 0) + 1
                entry = {
                    "url": item["url"], "author": item.get("author", ""),
                    "comment": item["comment"], "lang": item.get("lang", ""),
                    "fails": fails,
                }
                if rec.get("skipped") == "pending_author_approval":
                    # intentional skip: author-gated thread; never retry
                    entry["skip_reason"] = "pending_author_approval"
                if rec.get("error") == "post_deleted":
                    # post deleted between scrape and post; expected, not alertable
                    entry["skip_reason"] = "post_deleted"
                if not (err in RETRYABLE and fails < MAX_RETRIES):
                    # keep a tombstone so build_queue() cannot re-add this draft
                    # from comments.json (retry-loop bug 2026-09-29)
                    entry["dead"] = True
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
