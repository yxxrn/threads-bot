import json
from pathlib import Path

BOT = Path(__file__).resolve().parent
candidates = json.loads((BOT / "candidates.json").read_text())
replied = set(json.loads((BOT / "replied_urls.json").read_text()))
skip_urls = []
comments = []

id_promos = [
    "Kalau lagi serius bikin konten, cobain Blooply buat otomatis potong video panjang jadi shorts, cek profil aja.",
    "Duh ngerti banget, kerja sendiri emang capek kalau harus edit manual satu-satu. Kalau mau otomatis, Blooply bisa bantu potong video panjang jadi shorts, ada di profil.",
    "Wah seru nih diskusi, kadang ide datang pas gak prepare. Kalau nanti mau produksi video lebih cepat, Blooply bisa potong video panjang jadi shorts otomatis, ada di profil.",
    "Setuju banget soal hargain pekerja konten, mereka juga butuh waktu dan effort. Kalau butuh bantu produksi, Blooply potong video panjang jadi shorts otomatis, ada di profil.",
]
en_promos = [
    "If you end up creating any video content for your side hustle, Blooply can help cut long videos into shorts automatically, check my profile.",
    "Shift work makes it tough to find time for side projects, right? If you do end up making videos, Blooply cuts long recordings into shorts automatically, it's on my profile.",
    "Good question! If any side hustle idea leads to video content, Blooply automates cutting long videos into shorts, check my profile.",
]
idx_id = 0
idx_en = 0

for c in candidates:
    url = c["url"]
    author = c["author"]
    lang = c["lang"]
    text = c["text"].lower()

    # SKIP: political/content warning about Windah/rezim/protest
    if any(kw in text for kw in ["windah", "hack", "buzzer", "rezim", "boycoot", "protester", "state corruption", "forest fires", "indonesians first", "malaysian first"]):
        skip_urls.append(url)
        continue

    # SKIP: selling editing services (not hiring)
    if any(kw in text for kw in ["open jasa edit", "jasa edit video", "pricelist", "fee by dm"]):
        skip_urls.append(url)
        continue

    # SKIP: hiring non-editor (IT, sales, etc.)
    if any(kw in text for kw in ["backend developer", "frontend developer", "quality assurance", "technical writer", "loker", "lowongan"]):
        skip_urls.append(url)
        continue

    # SKIP: selling products (Mac Mini, etc.)
    if any(kw in text for kw in ["mac mini", "stok", "brand new in box", "segel"]):
        skip_urls.append(url)
        continue

    # SKIP: financial/loan spam
    if any(kw in text for kw in ["modal berapapun", "lunasin utang", "gas malem"]):
        skip_urls.append(url)
        continue

    # Generate comment
    if lang == "id":
        if "bisnis" in text or "modal 20 juta" in text or "jualan" in text:
            comment = f"Luar kuliner ternyata banyak juga peluangnya, menarik juga dipikirin. Kadang最难 justru eksekusi kalau modal terbatas. Kalau ujung-ujungnya bikin konten buat promosi, Blooply bisa bantu potong video panjang jadi shorts otomatis, ada di profil."
        elif "ai tools" in text or "rekomendasi ai" in text:
            comment = "AI buat kerjaan kantor emang makin banyak pilihannya sekarang. ChatGPT dan Gemini udah jadi favorit, tapi masih ada banyak tool lain yang worth dicoba. Kalau nanti ada materi video buat presentasi atau training, Blooply bisa potong video panjang jadi shorts otomatis, ada di profil."
        elif "content creator" in text or "kol specialist" in text or "barter" in text:
            comment = "Wah sedih sih kalau sampe dapat produk defect tapi仍 dimau banyak, creator juga perlu dihargain prosesnya. Semoga ke depannya kolaborasi lebih fair untuk kedua belah pihak. Kalau butuh bantu produksi, Blooply potong video panjang jadi shorts otomatis, ada di profil."
        else:
            comment = "Seru juga ya diskusi begituan, kadang ide-ide unik datang dari pertanyaan simpel. Semoga dapet jawaban yang bermanfaat buat semua. Kalau butuh bantu potong video panjang jadi shorts otomatis, Blooply ada di profil."
        comment += "\n\n" + id_promos[idx_id % len(id_promos)]
        idx_id += 1
    else:
        if "side hustle" in text or "extra income" in text:
            comment = "Shift work definitely makes side hustles tricky, but there are plenty of flexible options out there. If you end up creating any video content for your side hustle, Blooply can help cut long videos into shorts automatically, check my profile."
        else:
            comment = "Interesting perspective! Good luck with everything. If you ever need to cut long recordings into shorts, Blooply does it automatically, it's on my profile."
        comment += "\n\n" + en_promos[idx_en % len(en_promos)]
        idx_en += 1

    comments.append({"url": url, "author": author, "lang": lang, "comment": comment})

# Write files
(BOT / "comments_new.json").write_text(json.dumps(comments, ensure_ascii=False, indent=2))

existing_skips = []
skip_file = BOT / "skip_urls.txt"
if skip_file.exists():
    existing_skips = [l.strip() for l in skip_file.read_text().splitlines() if l.strip() and not l.strip().startswith("#")]
new_skips = sorted(set(existing_skips + skip_urls))
skip_file.write_text("\n".join(new_skips) + "\n")

print(f"WRITTEN: {len(comments)} comments to comments_new.json")
print(f"SKIPPED: {len(skip_urls)} URLs added to skip_urls.txt")
for s in skip_urls:
    print(f"  SKIP: {s}")
for c in comments:
    print(f"  KEEP: {c['url']} ({c['lang']})")
