import json
from pathlib import Path
BOT = Path(__file__).resolve().parent.parent  # reply-bot/
PICKS = [
"https://www.threads.com/@luxqib/post/DdzyDmBoNal",
"https://www.threads.com/@belladinnaafnan/post/Dd0hbRWCcsu",
"https://www.threads.com/@risna.sryni/post/DdzXmS_kz_i",
"https://www.threads.com/@vivianwijaya50/post/DdondklEzUZ",
"https://www.threads.com/@melinda_sita/post/Dd2p6j0EsMY",
"https://www.threads.com/@sandrella.official/post/Dd3dcOGkzw2",
"https://www.threads.com/@testingcatalog/post/Dd3nS7yAARj",
"https://www.threads.com/@berlianselnovik/post/Dd1mULUD21F",
"https://www.threads.com/@jus_dammy/post/Dd3LDxagAs5",
"https://www.threads.com/@edwarddowd_/post/Dd3BFZiFN-M",
"https://www.threads.com/@voitkornilova/post/Dd02dMQCDwt",
"https://www.threads.com/@thdxr/post/Dd1P2Mfls9h",
"https://www.threads.com/@trukhinyuri/post/DdwA89cCE7V",
"https://www.threads.com/@saadhjawwadh/post/Ddtv7ffCWwR",
"https://www.threads.com/@bizziology/post/DdmcY0pjZwv",
"https://www.threads.com/@tejastelkar9/post/Ddrytq6GZgM",
"https://www.threads.com/@ai.sahilbeniwal/post/Dd2d30gkwMc",
"https://www.threads.com/@nahiddotai/post/Dd10V49kuAK",
"https://www.threads.com/@zy65652/post/Dd3BDc2FVlm",
"https://www.threads.com/@michaelkaiserai/post/Dd1anexDVQG",
]

from cloakbrowser import launch
b = launch(headless=True, args=["--fingerprint=71529"])
ctx = b.new_context(storage_state=str(BOT / "state.json"))
page = ctx.new_page()
out = []
try:
    for u in PICKS:
        try:
            page.goto(u, timeout=90000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            info = page.evaluate("""() => {
                const og = document.querySelector(\x27meta[property="og:description"]\x27);
                const comp = document.querySelector("div[contenteditable=\x27true\x27][aria-label*=\x27text field\x27]");
                return {og: og?og.content:"", hasComposer: !!comp, title: document.title};
            }""")
            rec = {"url": u, "info": info}
            print("=" * 60)
            print(u, "| composer:", info["hasComposer"])
            print("OG:", info["og"][:420].replace(chr(10), " | "))
        except Exception as e:
            print("ERR", u, repr(e))
            rec = {"url": u, "info": {"error": str(e)}}
        out.append(rec)
finally:
    try:
        b.close()
    except Exception:
        pass
Path(BOT / "refill_check.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
print("DONE", len(out))
