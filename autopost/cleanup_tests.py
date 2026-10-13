from playwright.sync_api import sync_playwright
import time

# test roots to delete (wrong/experimental). KEEP: OK chain DdmC7f0kb8u + original user posts
TARGETS = [
    "https://www.threads.com/@blooplyy_/post/Ddl9FrqGH0c",  # MIX wrong (vid+foto in 1/3)
    "https://www.threads.com/@blooplyy_/post/DdmA0HwGCfD",  # FIX (foto hilang)
    "https://www.threads.com/@blooplyy_/post/DdmA0remLNF",  # FIX dup
    "https://www.threads.com/@blooplyy_/post/DdmCDfKGINx",  # DB
    "https://www.threads.com/@blooplyy_/post/DdmCi9JmEkb",  # DEC (missing part3)
]


def delete_current(page) -> str:
    mores = page.get_by_role("button", name="More")
    for i in range(mores.count()):
        bx = mores.nth(i)
        try:
            if not bx.is_visible():
                continue
            box = bx.bounding_box() or {}
            if not (60 <= box.get("y", 0) <= 300 and box.get("x", 0) > 600):
                continue
            bx.click(force=True)
            time.sleep(0.8)
            body = page.inner_text("body")
            if "Delete" in body and ("Insights" in body or "Archive" in body):
                page.get_by_text("Delete", exact=True).first.click()
                time.sleep(1)
                dlg = page.locator("[role=dialog]")
                if dlg.count():
                    dlg.get_by_role("button", name="Delete").last.click(force=True)
                else:
                    page.get_by_role("button", name="Delete").last.click(force=True)
                time.sleep(2.5)
                return "ok"
            page.keyboard.press("Escape")
            time.sleep(0.3)
        except Exception:
            continue
    return "fail"


with sync_playwright() as p:
    b = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
    c = b.new_context(storage_state="storage_state.json", viewport={"width": 1280, "height": 1200})
    page = c.new_page()
    for u in TARGETS:
        page.goto(u, wait_until="domcontentloaded")
        time.sleep(2.5)
        if "/post/" not in page.url:
            # try via profile click by text
            page.goto("https://www.threads.com/@blooplyy_", wait_until="domcontentloaded")
            time.sleep(3)
            slug = u.split("/post/")[-1
            ]
            txts = {"Ddl9FrqGH0c": "MIX 1/3", "DdmA0remLNF": "FIX 1/3"}
            t = txts.get(slug)
            try:
                if t and t in page.inner_text("body"):
                    page.get_by_text(t, exact=False).first.click()
                    time.sleep(2.5)
                else:
                    print(slug, "not on profile")
                    continue
            except Exception:
                print(slug, "click fail")
                continue
        if "/post/" not in page.url:
            print(u.split("/")[-1], "gone")
            continue
        print(u.split("/")[-1], delete_current(page))

    # verify leftovers on profile
    page.goto("https://www.threads.com/@blooplyy_", wait_until="domcontentloaded")
    time.sleep(4)
    body = page.inner_text("body")
    checks = ["MIX 1/3", "FIX 1/3", "DB 1/3", "DEC 1/3", "PROBE", "test post 221123", "OK 1/3"]
    print({k: (k in body) for k in checks})
    c.close()
    b.close()
