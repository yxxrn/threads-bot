#!/usr/bin/env python3
"""Generate comments_new.json from candidates with product matching and top-reply extra."""
import json
import subprocess
from pathlib import Path

BOT = Path(__file__).resolve().parent
candidates = json.loads((BOT / "candidates.json").read_text())
catalog = json.load(open(BOT / "catalog/catalog.json"))
offers = catalog["offers"]

SKIP_WORDS = [
    "presiden", "pajak", "korupsi", "tindak pidana", "buzzer", 
    "checkout marketplace", "income", "demo mahasiswa", "dibayar 100k",
    "bangkrut", "hutan gundul", "banjir bandang", "boikot", "wilson salim",
    "willie salim"
]

def should_skip(text):
    t = text.lower()
    return any(k in t for k in SKIP_WORDS)

def get_image(offer_id):
    img_dir = BOT / "catalog" / "images" / offer_id
    if img_dir.exists():
        imgs = list(img_dir.iterdir())
        if imgs:
            return str(imgs[0])
    return ""

def fetch_top_reply(url):
    """Fetch top reply for a post."""
    result = subprocess.run(
        ["python3", "fetch_top_reply.py", url],
        capture_output=True, text=True, cwd=BOT,
        env={**os.environ, "PYTHONPATH": str(BOT / "venv/lib/python3.11/site-packages")}
    )
    try:
        for line in result.stdout.split('\n'):
            if line.startswith('{'):
                return json.loads(line)
    except:
        pass
    return {"has_replies": False}

import os

def find_product(text):
    """Find best matching product from catalog."""
    t = text.lower()
    
    if any(k in t for k in ["hijab", "khimar", "bergo", "jilbab", "mukena"]):
        for o in offers:
            if any(k in o["name"].lower() for k in ["hijab", "khimar", "bergo"]):
                return o["offerId"], o["link"], get_image(o["offerId"])
    
    if any(k in t for k in ["tumbler", "botol", "minum", "thermos"]):
        for o in offers:
            if any(k in o["name"].lower() for k in ["tumbler", "botol"]):
                return o["offerId"], o["link"], get_image(o["offerId"])
    
    if any(k in t for k in ["jas hujan", "raincoat", "hujan"]):
        for o in offers:
            if "jas hujan" in o["name"].lower():
                return o["offerId"], o["link"], get_image(o["offerId"])
    
    if any(k in t for k in ["tas", "ransel", "dompet"]):
        for o in offers:
            if any(k in o["name"].lower() for k in ["tas", "ransel"]):
                return o["offerId"], o["link"], get_image(o["offerId"])
    
    if any(k in t for k in ["fashion", "blouse", "rok", "outfit"]):
        for o in offers:
            if any(k in o["name"].lower() for k in ["blouse", "rok", "fashion"]):
                return o["offerId"], o["link"], get_image(o["offerId"])
    
    if any(k in t for k in ["audio", "earphone", "headphone", "musik"]):
        for o in offers:
            if any(k in o["name"].lower() for k in ["audio", "earphone"]):
                return o["offerId"], o["link"], get_image(o["offerId"])
    
    # Default hijab
    for o in offers:
        if "hijab" in o["name"].lower():
            return o["offerId"], o["link"], get_image(o["offerId"])
    
    return None, None, ""

def gen_main_comment(c, product):
    """Generate main comment in Clove persona."""
    url = c["url"]
    author = c["author"]
    text = c["text"]
    t = text.lower()
    
    if product:
        oid, link, media = product
    else:
        link = "https://s.shopee.co.id/8AXFxpw0Rv"
        media = ""
    
    # Skip political content
    if any(k in t for k in ["kevin_konekzi", "boikot", "wilson salim", "willie salim"]):
        return None
    
    if any(k in t for k in ["demo mahasiswa", "trisakti", "dibayar 100k", "buzzer"]):
        return None
    
    if any(k in t for k in ["bangkrut", "hutan gundul", "banjir bandang"]):
        return None
    
    if any(k in t for k in ["ppn", "pajak pembulut", "judicial review"]):
        return None
    
    # Generate appropriate comment
    if "nadia omara" in t or "khw" in t or "tata" in t:
        comment = f"KHW emang seru banget, Nadia Omara selalu bikin kejutan yang bikin betah nonton. Semoga episodenya makin ramai! Btw, kalau mau tampil stylish pas nonton bareng keluarga, lagi ada promo hijab Khimar yang banyak dipilih: {link}"
    
    elif "dj" in t or "rans carnival" in t:
        comment = f"Rans Carnival emang selalu rame, line-up-nya selalu bikin kangen. Siapa tau tahun depan bisa ikutan lagi. Oh iya, buat dengerin musik perjalanan, lagi ada promo earphone yang worth it: {link}"
    
    elif "srk" in t or "shahrukh khan" in t:
        comment = f"SRK emang king-nya Bollywood, ga perlu franchise buat bikin penonton betah. Project Desember 2026 ini pasti rame! Btw, buat koleksi film-film favorit, lagi ada promo tas yang cozy: {link}"
    
    elif "grand opening" in t or "mc" in t or "event" in t:
        comment = f"Congrats buat PT SEKAWAN GLOBAL TEKNINDO! Grand opening emang momen spesial, MC yang tepat bisa bikin acara makin hidup. Semoga usahanya makin lancar! Oh iya, buat kebutuhan event lain juga lagi ada promo menarik: {link}"
    
    elif "japan matsuri" in t or "galaxy big band" in t:
        comment = f"Japan Matsuri emang always fun, apalagi ada GALAXY BIG BAND live. Suasana pasti meriah banget! Stay safe and enjoy the music ya. Btw, kalau lagi cari aksesori lengkap buat keluar, lagi ada promo: {link}"
    
    elif "blur" in t or "coffee and tv" in t.lower():
        comment = f"Coffee and TV, lyrics-nya emang timeless. Blur emang band yang ga pernah ketinggalan jaman. Seneng nemu threads yang rame soal musik retro gini. Oh iya, buat nemenin ngopi sore, lagi ada promo tumbler: {link}"
    
    elif "ai agent" in t or "webinar" in t:
        comment = f"AI agent yang bisa response kayak manusia emang masa depan yang menarik! Webinar Ayden pasti banyak insights-nya. Semoga makin banyak orang explore tech. Ngomong-ngomong, buat yang mau跟上 tren tech, lagi ada promo gadget: {link}"
    
    elif "double degree" in t or "kuliah" in t or "kampus" in t:
        comment = f"Double degree memang nggak gampang, tapi hasilnya pasti worth it. Semoga makin sukses! Buat nemenin aktivitas di kampus, tumbler yang tahan panas dingin ini enak banget buat daily use. Lagi ada promo menarik nih: {link}"
    
    elif "mancing" in t or "hobby" in t:
        comment = f"Mancing emang expenses-nya bisa nggak masuk akal kalau sudah serius hehe. Semoga suaminya tetap enjoy hobi ini. Buat bawa minuman saat mancing, tumbler ini cocok banget: {link}"
    
    elif "nasi" in t or "bantu" in t or "sedekah" in t:
        comment = f"Alhamdulillah, semoga kebaikan dilipatgandakan. Anak-anak itu juga dapat pelajaran berharga soal berbagi. Semoga rejekinya semakin berkah. Ngomong-ngomong, buat stok di rumah, gula pasir ini lagi promo: {link}"
    
    else:
        comment = f"Thanks for sharing! Topiknya menarik banget. Btw, ngomong-ngomong ada promo menarik nih yang lagi hits: {link}"
    
    return comment, link, media

def gen_extra_comment(c, top_reply, product):
    """Generate extra comment responding to top reply."""
    if not top_reply or not top_reply.get("has_replies"):
        return None
    
    top_text = top_reply.get("top_reply_text", "").lower()
    
    if product:
        oid, link, media = product
    else:
        link = "https://s.shopee.co.id/8AXFxpw0Rv"
    
    # Skip if top reply is in skip category
    if should_skip(top_reply.get("top_reply_text", "")):
        return None
    
    if "adopt" in top_text or "bocil" in top_text:
        extra = f"Setuju, anak kayak gini bikin bangga orang tuanya. Semoga makin sukses dan tetap rendah hati ya! Oh iya, buat yang mau cari tumbler bagus buat daily, lagi ada promo menarik: {link}"
    
    elif "supportive" in top_text or "baik banget" in top_text:
        extra = f"Iya, comments section ini pada supportive banget. Semoga usahanya lancar terus! Btw, buat yang butuh rak penyimpanan, lagi ada promo menarik: {link}"
    
    elif "promo" in top_text or "gratis" in top_text or "cuan" in top_text:
        extra = f"Yang penting belajar dengan niat baik, bukan cuma buat cuan. Semoga yang ikut dapat manfaat nyata. Btw, kalau mau tampil stylish pas kerja dari rumah, hijab ini lagi promo: {link}"
    
    elif "musik" in top_text or "lagu" in top_text or "band" in top_text:
        extra = f"Setuju, musik emang bahasa universal. Hope the concert was amazing! Oh iya, buat dengerin musik berkualitas, lagi ada promo earphone: {link}"
    
    elif "drama" in top_text or "sinetron" in top_text:
        extra = f"Iya nih, drama emang bikin ketagihan. Plot twist-nya selalu bikin deg-degan. Btw, kalau mau tampil stylish nonton bareng, lagi ada promo hijab: {link}"
    
    elif "ai" in top_text or "webinar" in top_text:
        extra = f"Setuju! AI agent yang bisa response kayak manusia emang keren. Semoga webinar berikutnya lebih lengkap lagi. Oh iya, buat yang mau跟上 tren tech, lagi ada promo gadget menarik: {link}"
    
    else:
        extra = f"Setuju banget sama komentar tadi! Btw, ngomong-ngomong ada promo menarik nih: {link}"
    
    return extra

# Process each candidate
comments = []
skipped = []

print("Fetching top replies and generating comments...")

for i, c in enumerate(candidates):
    print(f"\n[{i+1}/12] Processing {c['author']} ({c['lang']})")
    
    # Only Indonesian posts
    if c["lang"] != "id":
        print(f"  SKIP: non-ID post")
        continue
    
    # Check skip categories
    if should_skip(c["text"]):
        skipped.append((c["author"], "skip_words"))
        print(f"  SKIP: post in skip category")
        continue
    
    url = c["url"]
    author = c["author"]
    text = c["text"]
    
    # Fetch top reply
    print(f"  Fetching top reply...")
    tr = fetch_top_reply(url)
    has_replies = tr.get("has_replies", False)
    print(f"  Has replies: {has_replies}")
    
    # Find product
    product = find_product(text)
    if product:
        print(f"  Product: {product[0]}")
    
    # Generate main comment
    result = gen_main_comment(c, product)
    if result is None:
        skipped.append((author, "main_comment_skip"))
        print(f"  SKIP: main comment generation skipped")
        continue
    
    comment, link, media = result
    
    item = {
        "url": url,
        "author": author,
        "comment": comment,
        "lang": "id",
        "media_path": media
    }
    
    # Add extra comment if has replies
    if has_replies:
        extra = gen_extra_comment(c, tr, product)
        if extra:
            item["extra_comment"] = extra
            item["top_reply"] = {
                "author": tr.get("top_reply_author", ""),
                "text": tr.get("top_reply_text", ""),
                "url": tr.get("top_reply_url", "")
            }
            print(f"  Extra comment added")
        else:
            print(f"  No extra comment (skip category in top reply)")
    else:
        print(f"  No extra comment (no replies)")
    
    comments.append(item)
    print(f"  OK: main comment written")

print(f"\n{'='*50}")
print(f"Processed: {len(comments)} comments, {len(skipped)} skipped")
if skipped:
    print(f"Skipped: {[s[0] for s in skipped]}")

(BOT / "comments_new.json").write_text(json.dumps(comments, ensure_ascii=False, indent=2))
print(f"\nWritten {len(comments)} comments to comments_new.json")
