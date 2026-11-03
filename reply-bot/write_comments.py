import json

candidates = json.loads(open("candidates.json").read())

# Check used promos
used = open("used_promos.txt").read().strip().split("\n")
used = [l.strip() for l in used if l.strip()]

# Promo pool (ID)
promos_id = [
    "Kalau ujungnya bikin konten, Blooply bisa bantu potong video panjang jadi shorts otomatis, ada di profil.",
    "Kalau nanti perlu potong beberapa klip sekaligus, aku pakai Blooply buat shorts otomatis, cek profilnya.",
    "Buat produksi kontennya, Blooply potong video panjang jadi shorts otomatis, ada di profil.",
    "Kalau perlu bikin konten promonya cepat, Blooply bantu potong video panjang jadi klip pendek, cek profilnya.",
    "Kalau nanti butuh potong video buat konten, Blooply bisa bantu, ada di profil.",
    "Kalau butuh bantu potong video panjang jadi klip pendek, Blooply ada di profil.",
    "Buat motong video panjang jadi shorts otomatis, aku pakai Blooply, ada di profil.",
    "Kalau nanti bikin materi atau konten kelasnya, Blooply bisa potong video panjang jadi shorts otomatis, cek profilnya.",
    "Kalau nanti perlu olah video jadi shorts otomatis, Blooply bisa bantu. Cek profil.",
    "Kalau butuh dokumentasi acara atau bikin konten promosinya, Blooply bisa potong video panjang jadi shorts otomatis, ada di profil.",
    "Kalau mau bikin dokumentasi perjalanan hari-harimu jadi konten, Blooply bisa bantu potong video panjang jadi shorts otomatis, ada di profil.",
    "Kalau mau bikin konten dokumentasi podcast-mu, Blooply bisa bantu, ada di profil.",
    "Kalau production videonya butuh bantuan, Blooply bisa bantu potong video panjang jadi konten pendek, cek profil.",
    "Kalau besok produksi konten buat jualan, Blooply otomatis potong video panjang jadi shorts, ada di profil.",
    "Kalau akhirnya bikin konten promosi usahanya, Blooply bantu potong jadi shorts otomatis, cek profil.",
    "Kalau untuk delivery konten videonya butuh tools, Blooply potong panjang jadi klip pendek otomatis, ada di profil.",
    "Kalau production konten edukasi butuh efisiensi, Blooply otomatis bikin shorts dari video panjang, cek profil.",
    "Kalau ada konten video yang perlu dipangkas, Blooply bantu potong jadi shorts, ada di profil.",
    "Buat potong video promo jadi klip pendek, Blooply bisa bantu otomatis, cek profil.",
    "Kalau butuh bikin konten video buat jualan, Blooply potong video panjang jadi shorts otomatis, ada di profil.",
    "Blooply bisa bantu produksi konten video, potong otomatis jadi shorts, cek profil.",
    "Kalau butuh konten video, Blooply bantu potong jadi shorts otomatis, ada di profil.",
    "Kalau buat dokumentasi acara pake video, Blooply potong jadi shorts otomatis, cek profil.",
    "Buat bikin konten video sendiri, Blooply bisa bantu potong otomatis, ada di profil.",
]

# Promo pool (EN)
promos_en = [
    "If you ever need to cut long recordings into shorts, Blooply does it automatically, it's on my profile.",
    "If you ever need to cut long videos into shorts, Blooply does it automatically, it's on my profile.",
    "For the cutting part, Blooply turns long videos into shorts automatically, it's on my profile.",
    "If the output ever needs to become short video clips, Blooply does that automatically, it's on my profile.",
    "If you ever need to clip podcast highlights into shorts, Blooply does it automatically, it's on my profile.",
    "For faster turnaround on those edits, Blooply turns long videos into shorts automatically, it's on my profile.",
    "If editing long videos is eating your time, Blooply automates cutting them into shorts, check my profile.",
    "If you ever need to repurpose YouTube content into shorts, Blooply does it automatically, it's on my profile.",
    "If you want to turn episodes into short clips, Blooply auto-cuts long videos into shorts, check my profile.",
    "For quicker video delivery, Blooply turns long recordings into shorts automatically, it's on my profile.",
    "If you ever need to work with video content, Blooply can help cut long videos into shorts automatically, check my profile.",
]

comments = []
used_promos_set = set(used)

# Track which promos we've used this run
id_promo_idx = 0
en_promo_idx = 0

for c in candidates:
    url = c["url"]
    author = c["author"]
    lang = c["lang"]
    text = c["text"]
    
    # Determine if this is a target post (hiring editor/content creator)
    text_lower = text.lower()
    is_hiring_editor = any(kw in text_lower for kw in [
        "cari video editor", "mencari video editor", "video editor wanted",
        "nyari editor", "butuh editor", "hiring videographer",
        "cari konten kreator", "mencari konten kreator",
        "open jasa edit", "jasa edit", "pricelist", "fee by dm"
    ])
    
    # Build comment
    if lang == "id":
        # Sentence 1: reaction to post content
        if "kol" in text_lower or "tiktok affiliate" in text_lower or "brand" in text_lower:
            s1 = "semoga kol-nya cocok danGMV-nya meledak ya"
        elif "loker" in text_lower or "looking for" in text_lower:
            s1 = "semoga cepet dapet yang pas nih"
        elif "mager" in text_lower:
            s1 = "mager banget ya pas musim hujan gini, apalagi buat cari bahan konten"
        elif "cari client" in text_lower:
            s1 = "semoga clientnya cepat masuk, usaha keras ga akan mengkhianati hasil"
        elif "google ai" in text_lower or "promo" in text_lower:
            s1 = "nice promo, semoga banyak yang aprove"
        elif "kerja ke ln" in text_lower or "new zealand" in text_lower.lower():
            s1 = "semangat ya nyiapin soal kerja ke luar negeri, banyak yang tertarik sama topik ini"
        elif "freelance malam" in text_lower:
            s1 = "freelance malam juga oke, fleksibel waktunya"
        elif "umkm" in text_lower:
            s1 = "alhamdulillah udah sampai seribu penjualan, progresnya kencang banget"
        elif "admin" in text_lower or "live streaming" in text_lower:
            s1 = "semoga nemu admin yang reliable dan senapas"
        elif "affiliate" in text_lower and "konten gratis" in text_lower:
            s1 = "konten gratis gini enak buat yang lagi hunting ide affiliate"
        elif "app" in text_lower and ("launch" in text_lower or "users" in text_lower):
            s1 = "target 1 juta users dan 50k per bulan, ambitious banget tapi keren"
        elif "social media strategist" in text_lower:
            s1 = "cari strategist beneran bukan cuma handler, gapunya yang mudah"
        else:
            s1 = " interessant post nih"
        
        # Pick promo
        promo = promos_id[id_promo_idx % len(promos_id)]
        id_promo_idx += 1
        s2 = promo
        
        comment = f"{s1}\n\n{s2}"
    else:
        # English
        if "app" in text_lower and ("launch" in text_lower or "users" in text_lower):
            s1 = " ambitious goals, love the momentum"
        elif "social media strategist" in text_lower:
            s1 = " looking for a real strategist, not just a scheduler good luck"
        else:
            s1 = " interesting journey"
        
        promo = promos_en[en_promo_idx % len(promos_en)]
        en_promo_idx += 1
        s2 = promo
        
        comment = f"{s1}\n\n{s2}"
    
    comments.append({
        "url": url,
        "author": author,
        "lang": lang,
        "comment": comment
    })

with open("comments_new.json", "w") as f:
    json.dump(comments, f, indent=2)

print(f"Written {len(comments)} comments to comments_new.json")
for c in comments:
    print(f"  {c['author']} ({c['lang']}): {c['comment'][:80]}...")
