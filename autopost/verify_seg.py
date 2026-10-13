from playwright.sync_api import sync_playwright
import time, json, re, sys

url = sys.argv[1]

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
    c = b.new_context(storage_state="storage_state.json", viewport={"width": 1280, "height": 1600})
    page = c.new_page()
    page.goto(url, wait_until="domcontentloaded")
    time.sleep(4)
    if "/post/" not in page.url:
        root = url.split("/post/")[0]
        slug = url.split("/post/")[-1]
        page.goto(root, wait_until="domcontentloaded")
        time.sleep(4)
        # click first post link matching slug prefix
        page.locator(f'a[href*="{slug[:10]}"]').first.click()
        time.sleep(4)
    print("URL:", page.url)
    try:
        loc = page.get_by_text("View 1 more", exact=False)
        if loc.count():
            loc.first.click()
            time.sleep(1.5)
    except Exception:
        pass
    time.sleep(1)

    prefix = sys.argv[2] if len(sys.argv) > 2 else "OK"
    out = page.evaluate(
        """(prefix) => {
        const labels = [prefix + ' 1/3', prefix + ' 2/3', prefix + ' 3/3'];
        function findLab(lab) {
            let best = null;
            document.querySelectorAll('span,div').forEach((el) => {
                const t = (el.innerText || '').trim();
                if (t.indexOf(lab) === 0 && el.children.length <= 3) best = el;
            });
            return best;
        }
        const nodes = labels.map(findLab);
        function after(a, b) { return !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING); }
        const res = {labels: [], media: []};
        nodes.forEach((n, i) => res.labels.push({lab: labels[i], found: !!n}));
        const mediaEls = [];
        document.querySelectorAll('video').forEach((v) => mediaEls.push({k: 'VIDEO', el: v}));
        document.querySelectorAll('img').forEach((im) => {
            if (im.naturalWidth >= 300 && im.naturalHeight >= 200)
                mediaEls.push({k: 'IMG' + im.naturalWidth + 'x' + im.naturalHeight, el: im, src: (im.src || '').slice(-25)});
        });
        mediaEls.forEach((m) => {
            const r = m.el.getBoundingClientRect();
            if (r.width === 0) return;
            let seg = 'outside';
            for (let i = 0; i < nodes.length; i++) {
                if (!nodes[i]) continue;
                if (after(nodes[i], m.el)) {
                    const nextOk = (i + 1 >= nodes.length || !nodes[i + 1]) ? true : after(m.el, nodes[i + 1]);
                    if (nextOk) { seg = labels[i]; break; }
                    seg = 'between ' + labels[i] + ' and ' + (labels[i + 1] || 'end');
                }
            }
            res.media.push({seg, k: m.k, w: Math.round(r.width), h: Math.round(r.height), src: m.src || ''});
        });
        return res;
        }""",
        prefix,
    )
    print(json.dumps(out, indent=1))
    body = page.inner_text("body")
    badges = sorted(set(f"{a}/{b_}" for a, b_ in re.findall(r"(\d+)\s*/\s*(\d+)", body) if b_ == "3"))
    print("badges:", badges)
    texts = [f"{prefix} {i}/3" in body for i in (1, 2, 3)]
    print("parts present:", texts)
    page.screenshot(path="verify_ok.png", full_page=True)
    c.close()
    b.close()
