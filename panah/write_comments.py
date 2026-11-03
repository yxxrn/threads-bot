import json
import os

# Load catalog
with open('/home/agentuser/threads-bot-panah/catalog/catalog.json', 'r') as f:
    catalog = json.load(f)

# Load top reply results
top_replies = {
    "https://www.threads.com/@gimmecchocolate/post/DfK2cVhk2u8": {"has_replies": False, "reply_count": 0},
    "https://www.threads.com/@hrc_motogp/post/DfKTaglkq6x": {"has_replies": False, "reply_count": 0},
    "https://www.threads.com/@loramishra/post/DfKPcKbCZMf": {
        "has_replies": True,
        "reply_count": 3,
        "top_reply_author": "baishali.nath27",
        "top_reply_text": "Clip agey piche hota hai but insan toh same hai na 😂",
        "top_reply_url": "https://www.threads.com/@baishali.nath27/post/DfKRJsBifAB"
    },
    "https://www.threads.com/@collinveijerofficial/post/DfJ_SaFiKPR": {"has_replies": False, "reply_count": 0},
    "https://www.threads.com/@ridhwanrosli/post/DfJzhAYGH_K": {"has_replies": False, "reply_count": 0},
    "https://www.threads.com/@sinclairdarrel/post/DfJyrfeDIDq": {
        "has_replies": True,
        "reply_count": 1,
        "top_reply_author": "doobyis_",
        "top_reply_text": "So the people who defeated Bolsonaro in Brazil put out a document about how to beat the fascists...",
        "top_reply_url": "https://www.threads.com/@doobyis_/post/DfHxgkbG08o"
    }
}

# Catalog mapping for products
offers = catalog['offers']

# Product mapping by topic
products = {
    'sport': [offers[3], offers[4]],  # MODOFO Tumbler, Jas Hujan
    'fashion': [offers[1], offers[6], offers[28]],  # Hijab, Celana Kulot
    'general': [offers[3], offers[27]],  # Tumbler, Pashmina
    'racing': [offers[3], offers[4]],  # Tumbler, Jas Hujan
    'entertainment': [offers[1], offers[27]],  # Hijab, Pashmina
}

# Get image paths
def get_image_path(offer_id):
    img_dir = f"/home/agentuser/threads-bot-panah/catalog/images/{offer_id}"
    if os.path.exists(img_dir):
        files = os.listdir(img_dir)
        if files:
            return f"catalog/images/{offer_id}/{files[0]}"
    return ""

comments = []

# 1. gimmecchocolate - Bundesliga sport
c1 = {
    "url": "https://www.threads.com/@gimmecchocolate/post/DfK2cVhk2u8",
    "author": "gimmecchocolate",
    "lang": "id",
    "comment": "Nih, kalau lagi nonton bola malem-malem sambil ngemil, tumbler ini cocok banget buat nemenin! Bahannya stainless, tahan panas dingin, jadi minuman tetap segar sepanjang pertandingan 🍺 Linknya di sini ya, semoga membantu: https://s.shopee.co.id/9zyu9E6Urd",
    "media_path": get_image_path("53755077739"),
    "has_replies": False,
    "top_reply": None,
    "extra_comment": None
}
comments.append(c1)

# 2. hrc_motogp - MotoGP Sepang
c2 = {
    "url": "https://www.threads.com/@hrc_motogp/post/DfKTaglkq6x",
    "author": "hrc_motogp",
    "lang": "en",
    "comment": "Sepang circuit emang selalu seru buat balapan! Kalau mau nonton langsung, bawa jas hujan ya, cuaca bisa berubah tiba-tiba 🌧️ Sekarang lagi ada promo juga, bisa dicek langsung di sini: https://s.shopee.co.id/7AeilzI5i5",
    "media_path": get_image_path("41130989328"),
    "has_replies": False,
    "top_reply": None,
    "extra_comment": None
}
comments.append(c2)

# 3. loramishra - Bigg Boss entertainment
c3 = {
    "url": "https://www.threads.com/@loramishra/post/DfKPcKbCZMf",
    "author": "loramishra",
    "lang": "en",
    "comment": "Wah iya nih, emang sering ada editing yang bikin penasaran! Tapi tetap seru sih ngikutin aktris-actrisnya 👀 Oh iya, buat yang suka hijab rayon adem, ini rekomendasi bagus banget. Bahannya lembut dan sekarang lagi ada promo juga, cek langsung ya: https://s.shopee.co.id/8AXFxpw0Rv",
    "media_path": get_image_path("53966474374"),
    "has_replies": True,
    "top_reply": {"author": "baishali.nath27", "text": "Clip agey piche hota hai but insan toh same hai na 😂", "url": "https://www.threads.com/@baishali.nath27/post/DfKRJsBifAB"},
    "extra_comment": "Setuju banget, editing emang bisa bikin drama! Tapi yang penting tetap seru ditonton 😄 Ngomong-ngomong, kalau cari hijab yang adem buat daily, yang ini popular banget. Sekarang lagi diskon juga, mampir cek di sini ya: https://s.shopee.co.id/8AXFxpw0Rv"
}
comments.append(c3)

# 4. collinveijerofficial - F1 racing
c4 = {
    "url": "https://www.threads.com/@collinveijerofficial/post/DfJ_SaFiKPR",
    "author": "collinveijerofficial",
    "lang": "en",
    "comment": "P6 di QP, keren! 🏁 Semoga race-nya lancar dan bisa naik posisi ya. Buat nonton balap, bawa tumbler biar haus nggak genggam HP doang 😄 Link produknya: https://s.shopee.co.id/9zyu9E6Urd",
    "media_path": get_image_path("53755077739"),
    "has_replies": False,
    "top_reply": None,
    "extra_comment": None
}
comments.append(c4)

# 5. ridhwanrosli - MotoGP fashion tips
c5 = {
    "url": "https://www.threads.com/@ridhwanrosli/post/DfJzhAYGH_K",
    "author": "ridhwanrosli",
    "lang": "en",
    "comment": "Tipsnya mantap! Emang harus ringan aja pas ke MotoGP, capek bawa barang banyak 🏍️ Buat yang suka fashion simpel tapi syar'i, celana kulot ini nyaman banget buat jalan-jalan. Sekarang lagi ada promo, cek di sini ya: https://s.shopee.co.id/5q9LBgweDJ",
    "media_path": get_image_path("28961923123"),
    "has_replies": False,
    "top_reply": None,
    "extra_comment": None
}
comments.append(c5)

# 6. sinclairdarrel - social media algo
c6 = {
    "url": "https://www.threads.com/@sinclairdarrel/post/DfJyrfeDIDq",
    "author": "sinclairdarrel",
    "lang": "en",
    "comment": "Interesting insight tentang algorithm manipulation! Social media emang jadi battleground sekarang 📱 Ngomong-ngomong, buat daily use, tumbler aesthetic ini lagi hits. Sekarang lagi promo juga, mampir cek: https://s.shopee.co.id/9zyu9E6Urd",
    "media_path": get_image_path("53755077739"),
    "has_replies": True,
    "top_reply": {"author": "doobyis_", "text": "So the people who defeated Bolsonaro in Brazil put out a document about how to beat the fascists...", "url": "https://www.threads.com/@doobyis_/post/DfHxgkbG08o"},
    "extra_comment": "Iya banget, engagement itu kunci algoritma sekarang 👍 Kalau lagi cari referensi hijab rayon yang adem dan affordable, yang ini recommended banget. Linknya di sini, semoga membantu: https://s.shopee.co.id/8AXFxpw0Rv"
}
comments.append(c6)

# Write to comments_new.json
with open('/home/agentuser/threads-bot-panah/comments_new.json', 'w') as f:
    json.dump(comments, f, indent=2)

print(f"Wrote {len(comments)} comments to comments_new.json")
for c in comments:
    print(f"  - {c['author'][:20]:20s} | replies:{c['has_replies']} | extra:{c['extra_comment'] is not None}")
