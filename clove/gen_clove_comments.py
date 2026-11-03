#!/usr/bin/env python3
"""Generate Clove-style comments for Threads candidates."""
import json
from pathlib import Path
from datetime import datetime

BOT = Path(__file__).resolve().parent

# Load catalog
catalog = json.loads((BOT / "catalog/catalog.json").read_text())
offers = {o["offerId"]: o for o in catalog["offers"]}

# Check which offer IDs have images
image_dirs = list((BOT / "catalog/images").glob("*"))
offer_with_images = {d.name: f"catalog/images/{d.name}/1.jpg" for d in image_dirs if d.is_dir()}

# Load pool
pool = json.loads((BOT / "pool_ready.json").read_text())

# Load used URLs
queue = json.loads((BOT / "comments.json").read_text()) if (BOT / "comments.json").exists() else []
replied = set(json.loads((BOT / "replied_urls.json").read_text()) if (BOT / "replied_urls.json").exists() else [])
retry = json.loads((BOT / "retry_queue.json").read_text()) if (BOT / "retry_queue.json").exists() else []
dead = {r.get("url") for r in retry if isinstance(r, dict) and r.get("dead")}
queued = {c.get("url") for c in queue if c.get("url")}
used = replied | queued | dead

def norm_url(u):
    return str(u or "").replace("https://www.threads.com/", "https://threads.com/").replace("https://threads.net/", "https://threads.com/").rstrip("/")

used = {norm_url(u) for u in used}

# Skip keywords - comprehensive list for political/flame war/romance/income
SKIP_EXACT = [
    'buzzer', 'boikot', 'willy salim', 'rans carnival', 'demo mahasiswa', 
    'trisakti', 'saifulli', 'selingkuh', 'raffi ahmad', 'farid', 
    'kpk', 'bantuan', 'orderan fiktif', 'bantu beli', 'wts voucher',
    'terikatjanji', 'davina', 'pks', 'prabowo', 'lengser',
    'pmi', 'sri mulyani', 'anggota dpr', 'omnibus law',
    'sumpah pemuda', 'kehidupan beragama', 'islam',
    'rafatar', 'ayu tingting', 'nenek lo',
    'pak presiden', 'presiden', 'lema', 'lema lemo',
]

def is_skip(text):
    text_lower = text.lower()
    for kw in SKIP_EXACT:
        if kw in text_lower:
            return True
    return False

# Find good candidates
good = []
for p in pool:
    url = norm_url(p.get("url"))
    if url in used:
        continue
    if is_skip(p.get("text", "")):
        continue
    if p.get("lang") != "id":
        continue
    if len(p.get("text", "").strip()) < 20:
        continue
    good.append(p)

print(f"Found {len(good)} good candidates")

# Pick 12
picked = good[:12]
out = [{"url": p["url"], "author": p.get("author", ""), "lang": p.get("lang", "id"),
        "text": p.get("text", "")[:800]} for p in picked]
(BOT / "candidates.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))

# Product matching logic
def match_product(text, used_products):
    text_lower = text.lower()
    
    product_map = [
        ("hujan", "41130989328"),
        ("payung", "41759609032"),
        ("tumbler", "53755077739"),
        ("thermos", "47852223879"),
        ("botol minum", "42558437066"),
        ("sunscreen", "28218154859"),
        ("hijab", "53966474374"),
        ("bergo", "26783932942"),
        ("pashmina", "55258212427"),
        ("gamis", "53852319783"),
        ("dress", "56664503634"),
        ("blouse", "48505919896"),
        ("kemeja", "57664809912"),
        ("kulot", "28961923123"),
        ("sweater", "27952302574"),
        ("cardigan", "40461604896"),
        ("skincare", "1478747559"),
        ("lip cream", "3961474044"),
        ("blush", "14813718634"),
        ("cushion", "43464446853"),
        ("makeup", "24791849576"),
        ("parfum", "41830356970"),
        ("perfume", "44913159446"),
        ("wajan", "18012598053"),
        ("panci", "29435302861"),
        ("rak", "55667756643"),
        ("toples", "43651496518"),
        ("serbet", "52808896136"),
        ("sabun cuci", "54000299847"),
        ("tas", "55850049767"),
        ("sandal", "26226227964"),
        ("sepatu", "47251082581"),
        ("kacamata", "41752182705"),
        ("peniti", "48163627891"),
        ("anak", "47668083761"),
        ("boneka", "43208581827"),
        ("tisu", "29025107980"),
        ("pembersih", "26200503656"),
        ("nyamuk", "26200503656"),
    ]
    
    for keyword, offer_id in product_map:
        if keyword in text_lower and offer_id not in used_products:
            return offer_id
    
    # Default products
    for default_id in ["42558437066", "53755077739", "28961923123", "55850049767", "29025107980"]:
        if default_id not in used_products:
            return default_id
    
    return list(offers.keys())[0]

def generate_comment(candidate, offer_id, used_products):
    text = candidate["text"]
    author = candidate["author"]
    
    offer = offers.get(offer_id)
    if not offer:
        offer = list(offers.values())[0]
    
    link = offer["link"]
    name = offer["name"]
    text_lower = text.lower()
    
    # Extract key topic from post for specific reaction
    reaction = ""
    product_name = ""
    
    if "cfp" in text_lower or "sunscreen" in text_lower or "olahraga" in text_lower or "keringat" in text_lower:
        reaction = "Sunscreen emang wajib banget kalau aktif outdoor. Nanti kulit jadi kering dan terbakar."
        product_name = "Wardah Sunscreen"
    elif "remote" in text_lower or "freelance" in text_lower or "writer" in text_lower:
        reaction = "Remote job emang semakin populer. Pengalaman share selalu membantu yang lain."
        product_name = "Tumbler MODOFO"
    elif "viewer" in text_lower or "shadow banned" in text_lower or "naik tayang" in text_lower:
        reaction = "Algorithm Threads emang unik ya. Kadang konsisten tapi view nggak naik-naik."
        product_name = "Celana Kulot Hommy"
    elif "gold" in text_lower or "saham" in text_lower or "investasi" in text_lower:
        reaction = "Investasi emang penting buat masa depan. Tapi harus hati-hati pilih produknya."
        product_name = "Rak Troli Dapur"
    elif "parenting" in text_lower or "anak" in text_lower:
        reaction = " parenting emang nggak pernah berhenti belajarnya. Senang ada mom community yang sharing."
        product_name = "Mukena Anak Katun"
    elif "pks" in text_lower or "politik" in text_lower:
        reaction = "Diskusi politik emang selalu ramai. Penting buat tetap netral dan saling menghormati."
        product_name = "Celana Kulot Hommy"
    elif "wise" in text_lower or "dana" in text_lower or "transfer" in text_lower:
        reaction = "Digital payment emang praktis tapi kadang bisa error juga ya."
        product_name = "Dompet Wanita Inara"
    elif "hujan" in text_lower or "panas" in text_lower or "cuaca" in text_lower:
        reaction = "Cuaca ekstrem begini emang perlu persiapan. Jangan sampai kehabisan barang kebutuhan."
        product_name = "Jas Hujan"
    elif "aplikasi" in text_lower or "get contact" in text_lower or "penipu" in text_lower:
        reaction = "Aplikasi keamanan emang penting banget sekarang. Banyak penipuan yang semakin canggih."
        product_name = "Rak Troli Dapur"
    elif "iphone" in text_lower or "hp" in text_lower or "gadget" in text_lower:
        reaction = "Gadget terbaru emang menarik perhatian. Tapi pilih yang sesuai kebutuhan ya."
        product_name = "Kacamata Anti Radiasi"
    elif "bathroom" in text_lower or "cleaner" in text_lower or "bersih" in text_lower:
        reaction = "Cleaning tip emang selalu berguna. Rumah bersih bikin nyaman."
        product_name = "Sabun Cuci Piring"
    elif "magang" in text_lower or "maganghub" in text_lower:
        reaction = "Magang emang kesempatan bagus buat pengalaman. Proses seleksi emang kompetitif."
        product_name = "Toples Plastik"
    elif "dosen" in text_lower or "kuliah" in text_lower:
        reaction = "Kuliah emang fase penting. Semangat buat yang lagi kuliah!"
        product_name = "Tisu Jolly Pop Up"
    elif "donat" in text_lower or "jualan" in text_lower or "bisnis" in text_lower:
        reaction = "Support UMKM emang penting! Semoga jualan lancar terus."
        product_name = "Sabun Mandi Shinzui"
    elif "ramadhan" in text_lower or "lebaran" in text_lower or "ibadah" in text_lower:
        reaction = "Persiapan ibadah emang harus matang. Semangat menjalankan ibadah!"
        product_name = "Bergo Hamidah"
    elif "parlay" in text_lower or "betting" in text_lower:
        reaction = "Teman-teman emang suka diskusi soal olahraga. Tapi ingat tanggung jawab ya."
        product_name = "Boneka Fluffy"
    elif "tutorial" in text_lower or "cara" in text_lower or "tips" in text_lower:
        reaction = "Tutorial content emang selalu membantu. Share ilmu itu murah tapi bermanfaat."
        product_name = "Pashmina Sublime"
    elif "makan" in text_lower or "resep" in text_lower or "masak" in text_lower:
        reaction = "Masak emang hobi yang menyenangkan. Resep baru selalu seru dicoba."
        product_name = "Wajan Stainless"
    elif "travel" in text_lower or "liburan" in text_lower or "wisata" in text_lower:
        reaction = "Travel emang refreshing! Tempat mana yang lagi diincar?"
        product_name = "Tumbler 900ml"
    elif "makeup" in text_lower or "lip" in text_lower or "skincare" in text_lower:
        reaction = "Beauty routine emang penting. Produk apa saja yang jadi favorit?"
        product_name = "Hanasui Lip Cream"
    elif "tas" in text_lower or "fashion" in text_lower or "outfit" in text_lower:
        reaction = "Fashion always interesting topic. Outfit harian emang refleksi personality."
        product_name = "Tas Selempang Lalisa"
    else:
        # Generic but specific reaction - reference something from post
        first_line = text.split("\n")[0][:60] if "\n" in text else text[:60]
        reaction = f"Postingan yang menarik! {first_line}..."
        product_name = "Tumbler Aesthetic"
    
    # Add product link naturally
    comment = f"{reaction}\n\nNgomong-ngomong, {product_name} lagi ada promo lho, bisa dicek lewat link ini:\n{link}"
    
    return comment

# Generate comments
comments = []
used_products = set()

for candidate in out:
    offer_id = match_product(candidate["text"], used_products)
    used_products.add(offer_id)
    comment = generate_comment(candidate, offer_id, used_products)
    media_path = offer_with_images.get(offer_id, "")
    
    comments.append({
        "url": candidate["url"],
        "author": candidate["author"],
        "comment": comment,
        "lang": candidate["lang"],
        "media_path": media_path
    })

# Write comments_new.json
(BOT / "comments_new.json").write_text(json.dumps(comments, ensure_ascii=False, indent=2))
print(f"\nGenerated {len(comments)} comments -> comments_new.json")
print(f"Products used: {len(used_products)}")
print(f"Skipped from pool: {len(pool) - len(good)}")

# Print summary
for i, c in enumerate(comments):
    print(f"\n--- Comment {i+1} ---")
    print(f"URL: {c['url']}")
    print(f"Author: {c['author']}")
    print(f"Comment preview: {c['comment'][:120]}...")
