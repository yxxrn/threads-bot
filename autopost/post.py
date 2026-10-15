#!/usr/bin/env python3
"""Post text to Threads via Playwright. Needs storage_state.json.

Single:  post.py 'hello'
Chain:   post.py '1/N' '2/N' ...   # real thread (1/N badges), NOT reply spam
File:    post.py -f post.txt       # --- or blank line splits parts

Chain = multi-composer "Add to thread" then one Post. Client then
configure_text_only_post once per part (async). Must re-touch/blur each
slot before Post or Meta often only publishes first ~3.
Browser = CloakBrowser (stealth) first; stock chromium fallback.
"""
import argparse
import contextlib
import os
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PwTimeout
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "storage_state.json"
PROFILE = ROOT / "browser-data"
# keep playwright's stock browser inside the project (immune to ~/.cache cleaners)
if (ROOT / ".pw-browsers").exists():
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(ROOT / ".pw-browsers"))
PROFILE_URL = "https://www.threads.com/@blooplyy_"
# soft cap: web multi-composer works well; stress-tested to 15 with re-touch
MAX_PARTS = 25


def _dismiss(page) -> None:
    for name in ("Don't save", "Discard", "Not now", "Close", "OK"):
        try:
            b = page.get_by_role("button", name=name)
            if b.count() and b.first.is_visible(timeout=300):
                b.first.click(timeout=1500)
                time.sleep(0.2)
        except Exception:
            pass


def _open_composer(page) -> None:
    for loc in (
        page.get_by_role("button", name="New thread"),
        page.get_by_role("link", name="New thread"),
        page.locator('[aria-label="New thread"]'),
        page.locator('span:has-text("What\'s new?")'),
    ):
        try:
            if loc.count() and loc.first.is_visible():
                loc.first.click(timeout=5000)
                time.sleep(1.2)
                return
        except Exception:
            continue
    page.screenshot(path=str(ROOT / "debug_no_compose.png"), full_page=True)
    raise SystemExit("compose button not found → debug_no_compose.png")


def _click_post(page) -> None:
    posts = page.get_by_role("button", name="Post", exact=True)
    for i in range(posts.count()):
        b = posts.nth(i)
        try:
            if b.is_visible() and b.is_enabled() and (b.inner_text() or "").strip() == "Post":
                b.click(force=True)
                return
        except Exception:
            continue
    posts = page.get_by_role("button", name="Post")
    for i in range(posts.count()):
        b = posts.nth(i)
        try:
            if not b.is_visible() or not b.is_enabled():
                continue
            if (b.inner_text() or "").strip() == "Post Options":
                continue
            b.click(force=True)
            return
        except Exception:
            continue
    page.screenshot(path=str(ROOT / "debug_no_post.png"), full_page=True)
    raise SystemExit("Post button not found → debug_no_post.png")


def _editor_texts(page) -> list[str]:
    return page.evaluate(
        "() => [...document.querySelectorAll('[contenteditable=true]')].map(e => e.innerText || '')"
    )


def _fill_slot(page, index: int, text: str) -> None:
    for _ in range(40):
        if page.locator('[contenteditable="true"]').count() > index:
            break
        time.sleep(0.1)
    ed = page.locator('[contenteditable="true"]').nth(index)
    ed.scroll_into_view_if_needed()
    ed.click()
    time.sleep(0.15)
    ed.press_sequentially(text, delay=20)
    for _ in range(50):
        texts = _editor_texts(page)
        if index < len(texts) and text in texts[index]:
            break
        time.sleep(0.1)
    time.sleep(0.7)


def _add_slot(page) -> None:
    n = page.locator('[contenteditable="true"]').count()
    add = page.get_by_role("button", name="Add to thread")
    for _ in range(60):
        try:
            if add.count() and add.first.is_enabled():
                break
        except Exception:
            pass
        time.sleep(0.1)
    try:
        if not add.first.is_enabled():
            raise RuntimeError("disabled")
        add.first.click(timeout=8000)
    except Exception:
        page.screenshot(path=str(ROOT / "debug_no_add.png"), full_page=True)
        raise SystemExit("Add to thread failed → debug_no_add.png")
    page.wait_for_function(
        f'document.querySelectorAll("[contenteditable=true]").length > {n}',
        timeout=15_000,
    )
    time.sleep(0.9)


def _wait_post_enabled(page, timeout_s: int = 20) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            posts = page.get_by_role("button", name="Post", exact=True)
            for i in range(posts.count()):
                b = posts.nth(i)
                if b.is_visible() and b.is_enabled() and (b.inner_text() or "").strip() == "Post":
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def _attach_media(page, paths, slot: int = 0) -> None:
    """Attach 1+ images/videos to composer slot `slot` (multi-file = carousel)."""
    if not isinstance(paths, (list, tuple)):
        paths = [paths]
    paths = [Path(p) for p in paths]
    for p in paths:
        if not p.exists():
            raise SystemExit(f"media not found: {p}")
    is_video = any(p.suffix.lower() in {".mp4", ".mov", ".webm"} for p in paths)
    timeout_s = 90 if is_video else (60 if len(paths) > 1 else 30)
    hits = {"upload": 0}

    def on_res(r):
        u = r.url
        if any(x in u for x in ("rupload", "media/upload", "fbup", "upload_id")):
            try:
                if r.status < 400:
                    hits["upload"] += 1
            except Exception:
                pass

    page.on("response", on_res)
    try:
        # focus target slot so upload lands on that row
        ed = page.locator('[contenteditable="true"]').nth(slot)
        ed.click()
        time.sleep(0.25)
        if slot == 0:
            page.locator("input[type=file]").first.set_input_files([str(p) for p in paths])
        else:
            # row photo button: 36px leftmost toolbar btn inside THIS slot's
            # own row container. Find it by climbing from the slot's editor
            # until an ancestor holds ONLY this editor AND toolbar-sized
            # buttons (long text adds tall wrappers that must be skipped).
            # Then tag the button with an attribute and click via locator so
            # Playwright scrolls it into view (raw coords drift when the
            # composer scrolls — bug seen live 2026-10-06).
            # do NOT use [aria-label="Attach media"] — that's the ROOT
            # carousel "Add" and it dumps media into part 1.
            got = False
            for _try in range(4):
                chosen = page.evaluate(
                    """(i) => {
                      document.querySelectorAll('[data-blooply-photo]').forEach(
                        (e) => e.removeAttribute('data-blooply-photo'));
                      const eds = document.querySelectorAll('[contenteditable="true"]');
                      let el = eds[i];
                      for (let k = 0; k < 12 && el; k++) {
                        const inner = el.querySelectorAll('[contenteditable="true"]').length;
                        if (inner === 1 && el.getBoundingClientRect().height > 60) {
                          const bs = [];
                          el.querySelectorAll('button, [role=button]').forEach((btn) => {
                            const br = btn.getBoundingClientRect();
                            if (br.height < 25 || br.height > 60 || br.width > 48) return;
                            const svg = btn.querySelector('svg');
                            bs.push({
                              btn,
                              x: Math.round(br.left),
                              al: btn.getAttribute('aria-label') || '',
                              svgAl: svg ? (svg.getAttribute('aria-label') || '') : '',
                            });
                          });
                          const skip = new Set(["Close", "Add a GIF", "Add a sticker", "Add a location", "Add music"]);
                          const cands = bs.filter(
                            (b) => !skip.has(b.svgAl) && !b.al.includes('Attach media'));
                          if (cands.length) {
                            cands.sort((a, b) => a.x - b.x);
                            cands[0].btn.setAttribute('data-blooply-photo', '1');
                            return true;
                          }
                        }
                        el = el.parentElement;
                      }
                      return false;
                    }""",
                    slot,
                )
                if not chosen:
                    time.sleep(1.0)
                    continue
                try:
                    loc = page.locator('[data-blooply-photo="1"]')
                    loc.scroll_into_view_if_needed(timeout=4000)
                    with page.expect_file_chooser(timeout=8000) as fi:
                        loc.click(timeout=4000)
                    fi.value.set_files([str(p) for p in paths])
                    got = True
                    break
                except Exception as e:
                    print(f"  WARN: attach slot {slot} try {_try + 1}: {type(e).__name__}")
                    time.sleep(1.5)
            if not got:
                page.screenshot(path=str(ROOT / f"debug_no_attach_btn_slot{slot}.png"), full_page=True)
                raise SystemExit(f"row photo button for slot {slot} not found")
            # wait for preview INSIDE this row (global has_prev lies when
            # another slot already has media)
            ed_box = ed.bounding_box()
            deadline = time.time() + timeout_s
            while time.time() < deadline:
                found = page.evaluate(
                    """(i) => {
                      const eds = document.querySelectorAll('[contenteditable="true"]');
                      let el = eds[i];
                      for (let k = 0; k < 8 && el; k++) {
                        if (el.querySelectorAll('[contenteditable="true"]').length === 1
                            && el.getBoundingClientRect().height > 120) break;
                        el = el.parentElement;
                      }
                      if (!el) return false;
                      const vids = el.querySelectorAll('video').length;
                      const imgs = [...el.querySelectorAll('img')].some(
                        (x) => x.naturalWidth > 250 && x.getBoundingClientRect().height > 100
                      );
                      const blobs = [...el.querySelectorAll('img')].some(
                        (x) => (x.src || '').startsWith('blob:')
                      );
                      return vids > 0 || imgs || blobs;
                    }""",
                    slot,
                )
                if found:
                    break
                time.sleep(0.5)
            else:
                page.screenshot(path=str(ROOT / f"debug_no_preview_slot{slot}.png"), full_page=True)
                print(f"  WARN: no row preview confirmed for slot {slot}")
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                posts = page.get_by_role("button", name="Post", exact=True)
                pe = any(
                    posts.nth(i).is_visible() and posts.nth(i).is_enabled()
                    for i in range(posts.count())
                )
            except Exception:
                pe = False
            has_prev = page.locator("video, img[src*='blob:'], [data-media-id]").count() > 0
            if has_prev and (pe or hits["upload"]):
                break
            if pe and hits["upload"]:
                break
            time.sleep(0.5)
        time.sleep(1.5)
        print(f"  media[slot {slot}]: {', '.join(p.name for p in paths)} (video={is_video}, upload_hits={hits['upload']})")
        page.screenshot(path=str(ROOT / f"debug_media_slot{slot}.png"))
    finally:
        try:
            page.remove_listener("response", on_res)
        except Exception:
            pass


def _commit_all_slots(page, n: int) -> None:
    """Re-touch each slot so React queues configure for every part (critical for N>3)."""
    for i in range(n):
        ed = page.locator('[contenteditable="true"]').nth(i)
        ed.scroll_into_view_if_needed()
        ed.click()
        time.sleep(0.25)
        page.keyboard.press("End")
        time.sleep(0.15)
        page.evaluate(
            """(i) => {
              const el = document.querySelectorAll('[contenteditable=true]')[i];
              if (!el) return;
              // data MUST stay empty: Threads editor re-inserts insertText data
              // into the contenteditable, duplicating the whole part (seen 2026-09-23)
              el.dispatchEvent(new InputEvent('input', {
                bubbles: true, inputType: 'insertText', data: ''
              }));
              el.dispatchEvent(new Event('blur', {bubbles: true}));
            }""",
            i,
        )
        time.sleep(0.25)
    time.sleep(2.0)


def post_parts(
    parts: list[str],
    headless: bool = True,
    timeout_ms: int = 60_000,
    media: list[Path | None] | None = None,
) -> None:
    parts = [p.strip() for p in parts if p and p.strip()]
    if not parts:
        raise SystemExit("no text")
    if len(parts) > MAX_PARTS:
        raise SystemExit(f"max {MAX_PARTS} parts (got {len(parts)})")
    for p in parts:
        if len(p) > 500:
            raise SystemExit(f"part > 500 chars: {p[:40]!r}…")
    if not STATE.exists() and not PROFILE.exists():
        raise SystemExit("no session. run: python login.py / import cookies → storage_state.json")

    n = len(parts)
    # CloakBrowser first (stealth chromium, anti-bot fingerprint).
    # MUST launch before entering sync_playwright(): cloak spins its own
    # driver and errors with "Sync API inside the asyncio loop" otherwise.
    ctx = None
    browser = None
    page = None
    if os.environ.get("BLOOPLY_BROWSER") != "stock":
        try:
            from cloakbrowser import launch as _cloak_launch

            browser = _cloak_launch(
                headless=headless,
                args=["--disable-dev-shm-usage"],
            )
            ctx = browser.new_context(
                storage_state=str(STATE) if STATE.exists() else None,
                viewport={"width": 1280, "height": 900},
            )
            page = ctx.new_page()
            print("browser: cloakbrowser (stealth)")
        except Exception as e:
            # cloak leaves a live asyncio loop on failure; sync_playwright
            # refuses to start in it → re-exec once with stock chromium
            print(f"browser: cloak failed ({e.__class__.__name__}: {e}) → restart stock")
            os.environ["BLOOPLY_BROWSER"] = "stock"
            os.execv(sys.executable, [sys.executable, *sys.argv])
    stack = contextlib.ExitStack()
    with stack:
        if ctx is None:
            p = stack.enter_context(sync_playwright())
            if PROFILE.exists():
                ctx = p.chromium.launch_persistent_context(
                    user_data_dir=str(PROFILE),
                    headless=headless,
                    viewport={"width": 1280, "height": 900},
                    args=["--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage"],
                )
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
            else:
                browser = p.chromium.launch(
                    headless=headless,
                    args=["--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage"],
                )
                ctx = browser.new_context(
                    storage_state=str(STATE),
                    viewport={"width": 1280, "height": 900},
                )
                page = ctx.new_page()

        page.set_default_timeout(timeout_ms)
        configs: list[str] = []

        def on_req(r):
            if r.method == "POST" and "configure_text" in r.url:
                m = re.search(r"caption=([^&]*)", r.post_data or "")
                if m:
                    from urllib.parse import unquote_plus

                    configs.append(unquote_plus(m.group(1)))

        page.on("request", on_req)

        page.goto("https://www.threads.com/", wait_until="domcontentloaded")
        time.sleep(2)
        _dismiss(page)
        _open_composer(page)
        _dismiss(page)

        media = media or []

        def _m(i: int) -> Path | None:
            return media[i] if i < len(media) else None

        # NOTE: attach media BEFORE typing when a part contains a URL.
        # Threads renders a big link-preview card the moment a link is typed,
        # which pushes/overlays the per-row toolbar and makes the slot-1
        # "row photo" button unfindable (attach loop times out, seen
        # 2026-10-15 with the t.me/satudigitalbot link in part 2).
        link_any = any(re.search(r"https?://|t\.me/|\.com/|\.ai/", p) for p in parts)
        if link_any:
            if _m(0):
                _attach_media(page, _m(0), 0)
            for i in range(1, n):
                _add_slot(page)
                if _m(i):
                    _attach_media(page, _m(i), i)
            for i, part in enumerate(parts):
                _fill_slot(page, i, part)
        else:
            _fill_slot(page, 0, parts[0])
            if _m(0):
                _attach_media(page, _m(0), 0)
            for i, part in enumerate(parts[1:], start=1):
                _add_slot(page)
                _fill_slot(page, i, part)
                if _m(i):
                    _attach_media(page, _m(i), i)

        texts = _editor_texts(page)
        if len(texts) < n or any(parts[i] not in texts[i] for i in range(n)):
            page.screenshot(path=str(ROOT / "debug_parts_mismatch.png"), full_page=True)
            raise SystemExit(f"composer mismatch {texts!r} vs {parts!r}")

        _commit_all_slots(page, n)
        # dup guard post-commit: first line of each part must appear exactly
        # once per editor (commit/insertText race can duplicate paragraphs,
        # seen live on 2026-09-23 promo part 3)
        texts = _editor_texts(page)
        for i, want in enumerate(parts):
            prefix = next((ln for ln in want.splitlines() if ln.strip()), want)[:40].strip()
            hay = texts[i] if i < len(texts) else ""
            cnt = hay.count(prefix)
            if cnt != 1:
                page.screenshot(path=str(ROOT / "debug_dup_text.png"), full_page=True)
                raise SystemExit(f"slot {i} text {cnt}x before Post (want 1x) → debug_dup_text.png")
        page.locator('[contenteditable="true"]').first.click()
        time.sleep(0.3)
        if not _wait_post_enabled(page, 90 if any(media or []) else 20):
            page.screenshot(path=str(ROOT / "debug_post_disabled.png"), full_page=True)
            raise SystemExit("Post button never enabled → debug_post_disabled.png")
        _click_post(page)

        # wait for one configure per part (async)
        deadline = time.time() + max(20, 4 * n)
        while time.time() < deadline and len(configs) < n:
            time.sleep(0.5)
        print(f"  configure_calls={len(configs)}/{n}")

        try:
            page.wait_for_load_state("networkidle", timeout=15_000)
        except PwTimeout:
            pass
        time.sleep(max(5, n))
        _dismiss(page)
        page.screenshot(path=str(ROOT / "last_post.png"))

        try:
            page.goto(PROFILE_URL, wait_until="domcontentloaded")
            time.sleep(3)
            page.get_by_text(parts[0][:40], exact=False).first.click(timeout=12_000)
            time.sleep(4)
            for _ in range(max(4, n)):
                page.mouse.wheel(0, 1600)
                time.sleep(0.25)
            body = page.inner_text("body")
            page.screenshot(path=str(ROOT / "last_post_profile.png"), full_page=True)
            # normalize whitespace: Threads collapses blank lines on render,
            # comparing raw text gives false "missing" (seen 2026-10-06)
            norm = lambda s: re.sub(r"\s+", " ", s).strip()
            body_n = norm(body)
            miss = [x for x in parts if norm(x) not in body_n]
            fracs = re.findall(r"(\d+)\s*/\s*(\d+)", body)
            has_nn = any(a == str(n) and b == str(n) for a, b in fracs)
            if miss:
                print(f"WARN missing ({len(miss)}/{n}): {miss!r}")
            elif not has_nn and n > 1:
                print(f"WARN no {n}/{n} badge (fracs={fracs[:12]}) — may be replies not chain")
            else:
                print(f"ok chain ({n} parts, badges ok) → last_post_profile.png")
            print("url", page.url)
        except Exception as e:
            print(f"posted, verify fail: {e} → last_post.png")

        try:
            # only persist refreshed cookies when actually logged in, so a
            # dead-session run can't overwrite storage_state with logout junk
            if page.get_by_role("button", name="New thread").count():
                ctx.storage_state(path=str(STATE))
        except Exception:
            pass
        try:
            ctx.close()
        except Exception:
            pass
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass


def _parts_from_file(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8")
    if "\n---\n" in raw:
        return [s.strip() for s in raw.split("\n---\n") if s.strip()]
    chunks, buf = [], []
    for line in raw.splitlines():
        if line.strip() == "":
            if buf:
                chunks.append("\n".join(buf).strip())
                buf = []
        else:
            buf.append(line)
    if buf:
        chunks.append("\n".join(buf).strip())
    return chunks or ([raw.strip()] if raw.strip() else [])


def main() -> None:
    global STATE, PROFILE_URL
    ap = argparse.ArgumentParser(description="Post to Threads (single or real multi-part chain)")
    ap.add_argument("parts", nargs="*", help="parts → one chain with 1/N…N/N")
    ap.add_argument("-f", "--file", type=Path, help="file; --- or blank line splits parts")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument(
        "--state",
        type=Path,
        default=None,
        help="storage_state path (default storage_state.json; profil2: storage_state_p2.json)",
    )
    ap.add_argument(
        "--profile-url",
        default=None,
        help="URL profil untuk verifikasi pasca-post (default: @blooplyy_)",
    )
    ap.add_argument(
        "--media",
        action="append",
        type=str,
        help="media per part (repeatable, order=part index); koma = carousel multi-file (a.jpg,b.jpg); '-' = tanpa media",
    )
    args = ap.parse_args()
    if args.state:
        STATE = args.state
    if args.profile_url:
        PROFILE_URL = args.profile_url
    parts = _parts_from_file(args.file) if args.file else list(args.parts)
    if not parts:
        sys.exit(
            "usage: post.py 'a' ['b' ...] | post.py -f file.txt\n"
            "       --media file.mp4 --media photo.jpg --media -   (per part)\n"
            "       --media a.jpg,b.jpg  (carousel 2+ gambar dalam 1 bagian)"
        )
    media = []
    for m in args.media or []:
        if m in (None, "", "-"):
            media.append(None)
        else:
            media.append([Path(x.strip()) for x in m.split(",") if x.strip()])
    post_parts(parts, headless=not args.headed, media=media)


if __name__ == "__main__":
    main()
