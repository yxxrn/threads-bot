#!/usr/bin/env python3
"""Build comments_new.json for Panah Threads bot - V2 with top-reply support."""
import json
import random
from pathlib import Path

BOT = Path(__file__).resolve().parent

# Load catalog
with open(BOT / 'catalog/catalog.json') as f:
    catalog = json.load(f)
offers = catalog.get('offers', [])
offer_map = {o['offerId']: o for o in offers}

# Load candidates
with open(BOT / 'candidates.json') as f:
    candidates = json.load(f)

# Load replied URLs
replied = set()
try:
    with open(BOT / 'replied_urls.json') as f:
        replied = set(json.load(f))
except:
    pass

# Skip keywords for posts (NOT for top replies)
SKIP_KW = [
    'korupsi', 'prabowo', 'pilkada', 'dpr', 'politik', 'curang', 'selingkuh',
    'pacar', 'mantan', 'breakup', 'penghasilan', 'cuma', 'modal', 'bisnis online',
    'shopee affiliate', 'cancer', 'sakit', 'penyakit', 'rawatan', 'berlepas',
    'china', 'hospital', 'rumah sakit', 'demo', 'protes', 'gubernur', 'wali kota',
    'bupati', 'presiden', 'coblos', 'pajak rakyat', 'hancur', 'maga', 'trump',
    'midterms', 'election', 'political', 'shibuya', 'maut', 'meninggal', 'dukacita',
    'penyakit kanker', 'kanker'
]

def is_skip_post(text):
    text_lower = text.lower()
    return any(kw in text_lower for kw in SKIP_KW)

def get_image_path(offer_id):
    """Get image path for offer - check actual filename."""
    img_dir = BOT / 'catalog' / 'images' / offer_id
    if img_dir.exists():
        files = sorted(img_dir.glob('*.jpg')) + sorted(img_dir.glob('*.png'))
        if files:
            return str(files[0])
    return ""

def find_relevant_product(post_text, exclude_ids=None):
    """Find best matching product from catalog for post topic."""
    exclude_ids = exclude_ids or []
    text_lower = post_text.lower()
    
    matches = []
    for o in offers:
        if o['offerId'] in exclude_ids:
            continue
        name = o['name'].lower()
        score = 0
        
        # Category matching
        if any(k in text_lower for k in ['tumbler', 'botol', 'minum', 'adem', 'dingin']):
            if any(k in name for k in ['tumbler', 'botol', 'minum', 'thermos']):
                score += 15
        if any(k in text_lower for k in ['hijab', 'bergo', 'rayon', 'khimar']):
            if any(k in name for k in ['hijab', 'bergo', 'rayon', 'khimar']):
                score += 15
        if any(k in text_lower for k in ['parfum', 'wangi']):
            if any(k in name for k in ['parfum', 'perfume', 'wangi']):
                score += 15
        if any(k in text_lower for k in ['jas hujan', 'hujan', 'raincoat']):
            if any(k in name for k in ['jas hujan', 'raincoat']):
                score += 15
        if any(k in text_lower for k in ['buku', 'reading']):
            if 'buku' in name:
                score += 15
        if any(k in text_lower for k in ['tas', 'bag']):
            if any(k in name for k in ['tas', 'bag']):
                score += 15
        
        # Generic fallback
        if score == 0:
            if any(k in name for k in ['parfum', 'hijab', 'gula', 'sabun', 'tisu', 'kaos', 'tumbler']):
                score = 2
        
        if score > 0:
            matches.append((score, o['offerId'], o))
    
    if not matches:
        # Fallback: pick popular generic item
        for o in offers:
            if o['offerId'] not in exclude_ids:
                name = o['name'].lower()
                if any(k in name for k in ['parfum', 'hijab', 'gula', 'sabun', 'tisu', 'kaos', 'tumbler']):
                    return o
        for o in offers:
            if o['offerId'] not in exclude_ids:
                return o
        return None
    
    matches.sort(key=lambda x: x[0], reverse=True)
    return matches[0][2]

def generate_main_comment(post, offer, idx):
    """Generate Panah persona main comment in Indonesian."""
    text = post['text']
    offer_name = offer['name']
    link = offer['link']
    text_lower = text.lower()
    
    # Varied openers based on post content
    openers = []
    
    if 'tumbler' in text_lower or 'adem' in text_lower or 'dingin' in text_lower:
        openers = [
            f"Nih, buat temen ngopi atau minum air dingin seharian, tumbler stainless ini pas banget. Bahannya tahan panas dan dingin sampai 24 jam, jadi minuman tetap segar. Sekarang lagi ada promo juga, bisa dicek langsung di sini ya, semoga membantu: {link}",
            "Kalo lagi cari tumbler yang awet dan harganya ramah di kantong, yang ini rekomendasi! Desainnya aesthetic dan fungsinya lengkap. Lagi diskon menarik nih, cek di sini ya: {link}",
            "Wah, lagi nyari tumbler juga nih. Yang ini banyak yang suka karena materialnya stainless steel, adem buat cairan dingin. Promo lagi jalan, mampir cek dulu ya: {link}",
        ]
    elif 'gumroad' in text_lower or 'ebook' in text_lower or 'jualan' in text_lower:
        openers = [
            f"Seru nih belajar jualan digital! Kalau butuh inspirasi produk digital lain, coba cek marketplace. Lagi ada promo menarik juga, semoga membantu: {link}",
            "Belajar gumroad memang seru ya, tapi jangan lupa persiapan produknya juga. Kalau mau liat produk digital lain yang lagi hits, cek di sini: {link}",
        ]
    elif 'bioskop' in text_lower or 'nonton' in text_lower or 'film' in text_lower:
        openers = [
            f"Nonton bioskop emang asik, apalagi kalau dapat promo! Buat nambah hemat lagi, ada banyak produk menarik yang lagi diskon. Cek di sini ya: {link}",
            "Bioskop + pop corn = combo sempurna! Kalau mauhemat lagi, ada banyak promo menarik. Salah satunya bisa dicek di sini: {link}",
        ]
    elif 'promo' in text_lower or 'shopee' in text_lower:
        openers = [
            f"Iya nih, belanja di Shopee emang perlu timing yang pas! Kalau lagi cari produk lainnya yang lagi promo, ada banyak pilihan menarik. Cek di sini ya: {link}",
            "Betul banget, tau waktu promo itu penting! Buat yang mau nambah hemat lagi, ada produk-produk menarik yang lagi diskon. Cek: {link}",
        ]
    else:
        openers = [
            f"Postingannya menarik! Kalau lagi cari produk lain yang worth it, ada rekomendasi buat kamu. Lagi ada promo juga, cek di sini ya: {link}",
            "Sama nih, sering banget nemu hal menarik di Threads. Buat yang mau liat produk menarik lainnya, ada promo spesial nih: {link}",
            "Wah, postingannya bikin tertarik! Kalau butuh produk lain yang kualitasnya oke, coba cek ini. Lagi ada penawaran menarik: {link}",
        ]
    
    # Select opener based on index
    opener = openers[idx % len(openers)].format(link=link)
    
    return opener

def generate_extra_comment(offer, top_reply_text=None):
    """Generate extra comment responding to top reply but anchored to post topic."""
    link = offer['link']
    offer_name = offer['name']
    
    # Generic but natural extra comments that reference product category
    extras = [
        f"Ngomong-ngomong, kalau lagi cari produk lain yang lagi promo, yang ini cocok banget buat daily use. Worth it dicoba, cek langsung di sini ya: {link}",
        "Btw, ada produk lain yang lagi diskon menarik. Bahannya adem dan nyaman, bisa jadi tambahan rekomendasi. Cek di sini: {link}",
        "Oh iya, kalau butuh produk yang lagi murah dan berkualitas, yang ini lagi banyak peminatnya. Link-nya ada di sini ya: {link}",
    ]
    
    return random.choice(extras)

# Filter eligible Indonesian posts
eligible = []
for c in candidates:
    if c.get('lang') != 'id':
        continue
    if c['url'] in replied:
        continue
    if is_skip_post(c.get('text', '')):
        continue
    eligible.append(c)

print(f"Eligible ID posts: {len(eligible)}")

# Shuffle for variety
random.seed()
random.shuffle(eligible)

# Select up to 12 candidates
selected = eligible[:12]

# Load top replies if available (from previous runs or cache)
top_replies = {}
try:
    with open(BOT / 'top_replies_cache.json') as f:
        top_replies = json.load(f)
except:
    pass

# Build comments
comments = []
exclude_ids = []

for idx, post in enumerate(selected):
    url = post['url']
    author = post['author']
    text = post['text']
    
    # Find relevant product
    offer = find_relevant_product(text, exclude_ids)
    
    if not offer:
        print(f"  SKIP @{author}: no product found")
        continue
    
    exclude_ids.append(offer['offerId'])
    
    # Generate main comment
    main_comment = generate_main_comment(post, offer, idx)
    
    # Get image path
    image_path = get_image_path(offer['offerId'])
    
    # Check for top reply
    extra_comment = ""
    top_reply = None
    if url in top_replies:
        tr = top_replies[url]
        if tr.get('has_replies') and tr.get('reply_count', 0) > 0:
            top_reply = {
                'url': tr.get('top_reply_url', ''),
                'author': tr.get('top_reply_author', ''),
                'text': tr.get('top_reply_text', '')
            }
            # Generate extra comment only if there's a top reply
            if top_reply['text']:
                extra_comment = generate_extra_comment(offer, top_reply['text'])
    
    # Build item
    item = {
        'url': url,
        'author': author,
        'comment': main_comment,
        'lang': 'id',
        'media_path': image_path
    }
    
    if extra_comment:
        item['extra_comment'] = extra_comment
        item['top_reply'] = top_reply
    
    comments.append(item)
    print(f"  [{idx+1}] @{author}: {text[:50]}...")
    print(f"      -> Product: {offer['name'][:50]}...")
    print(f"      -> Comment: {main_comment[:80]}...")
    if extra_comment:
        print(f"      -> Extra: {extra_comment[:80]}...")

# Write output
with open(BOT / 'comments_new.json', 'w', encoding='utf-8') as f:
    json.dump(comments, f, ensure_ascii=False, indent=1)

print(f"\nWrote {len(comments)} comments to comments_new.json")
print(f"Used {len(exclude_ids)} unique products")
