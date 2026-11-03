#!/usr/bin/env python3
"""Build comments_new.json for Panah Threads bot refill (simplified, no top-reply fetch)."""
import json
import random
from pathlib import Path

BOT = Path(__file__).resolve().parent

# Load catalog
with open(BOT / 'catalog/catalog.json') as f:
    catalog = json.load(f)
offers = catalog.get('offers', [])

# Load pool
with open(BOT / 'pool_ready.json') as f:
    pool = json.load(f)

# Load replied URLs
replied = set()
try:
    with open(BOT / 'replied_urls.json') as f:
        replied = set(json.load(f))
except:
    pass

# Skip keywords
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
        if 'mainan' in text_lower and ('mainan' in name or 'toy' in name or 'anak' in name):
            score += 10
        if any(k in text_lower for k in ['makeup', 'perawatan', 'kulit', 'skincare']):
            if any(k in name for k in ['lip', 'parfum', 'cream', 'makeup', 'beauty', 'skincare']):
                score += 10
        if any(k in text_lower for k in ['sepatu', 'sandal']):
            if any(k in name for k in ['sepatu', 'sandal', 'shoe']):
                score += 10
        if any(k in text_lower for k in ['rayon', 'one set', 'hijab', 'bergo']):
            if any(k in name for k in ['rayon', 'hijab', 'bergo', 'khimar']):
                score += 10
        if 'softlens' in text_lower:
            if 'softlens' in name or 'lens' in name:
                score += 10
        if 'parfum' in text_lower:
            if 'parfum' in name or 'perfume' in name or 'wangi' in name:
                score += 10
        if any(k in text_lower for k in ['tumbler', 'botol', 'minum']):
            if any(k in name for k in ['tumbler', 'botol', 'minum']):
                score += 10
        if any(k in text_lower for k in ['tas', 'bag']):
            if any(k in name for k in ['tas', 'bag']):
                score += 10
        if any(k in text_lower for k in ['buku', 'reading']):
            if 'buku' in name:
                score += 10
        if 'jas hujan' in text_lower or 'hujan' in text_lower:
            if 'jas hujan' in name or 'raincoat' in name:
                score += 10
        if any(k in text_lower for k in ['tanaman', 'houseplant', 'indoor']):
            if any(k in name for k in ['tanaman', 'pot', 'flower', 'plant']):
                score += 10
        if 'power bank' in text_lower or 'charger' in text_lower:
            if 'power bank' in name or 'charger' in name:
                score += 10
        if any(k in text_lower for k in ['kado', 'hadiah', 'gift']):
            if any(k in name for k in ['gift', 'hadiah', 'kado']):
                score += 10
        
        # Generic fallback
        if score == 0:
            if any(k in name for k in ['gula', 'sabun', 'tisu', 'parfum', 'hijab', 'kulot', 'kaos', 'cellphone', 'case', 'earphone']):
                score = 1
        
        if score > 0:
            matches.append((score, o['offerId'], o))
    
    if not matches:
        # Fallback: pick popular generic item
        for o in offers:
            if o['offerId'] not in exclude_ids:
                name = o['name'].lower()
                if any(k in name for k in ['parfum', 'hijab', 'gula', 'sabun', 'tisu', 'kaos']):
                    return o
        for o in offers:
            if o['offerId'] not in exclude_ids:
                return o
        return None
    
    matches.sort(key=lambda x: x[0], reverse=True)
    return matches[0][2]

def get_image_path(offer_id):
    """Get image path for offer - check actual filename."""
    img_dir = BOT / 'catalog' / 'images' / offer_id
    if img_dir.exists():
        files = list(img_dir.glob('*.jpg')) + list(img_dir.glob('*.png'))
        if files:
            return str(files[0])
    return ""

def generate_comment(post, offer, idx):
    """Generate Panah persona comment in Indonesian."""
    text = post['text']
    offer_name = offer['name']
    link = offer['link']
    text_lower = text.lower()
    
    # Extract specific details from post for reaction
    details = []
    if 'tanaman' in text_lower or 'houseplant' in text_lower or 'indoor' in text_lower:
        details.append('tanaman hias indoor')
    elif 'jajan karet' in text_lower:
        details.append('jajan karet')
    elif 'power bank' in text_lower or 'fast charging' in text_lower:
        details.append('power bank')
    elif 'buku' in text_lower or 'nitip buku' in text_lower:
        details.append('buku')
    elif 'tas' in text_lower:
        details.append('tas')
    elif 'sepatu' in text_lower:
        details.append('sepatu')
    elif 'hijab' in text_lower or 'rayon' in text_lower or 'bergo' in text_lower:
        details.append('hijab rayon')
    elif 'parfum' in text_lower:
        details.append('parfum')
    elif 'hujan' in text_lower or 'jas hujan' in text_lower:
        details.append('jas hujan')
    
    # Templates with varied openers
    templates = [
        ("Nih, kalau lagi cari {detail} yang worth it...", " Bahannya adem dan nyaman banget buat daily."),
        ("Kalo lagi butuh {detail} yang oke...", " Reviewnya bagus-bagus, banyak yang repurchase."),
        ("Wah ini recommended banget buat {detail}...", " Desainnya kece, cocok buat aktivitas harian."),
        ("Sama nih, lagi nyari {detail} juga...", " Worth it banget kalo dipake sehari-hari."),
        ("Ini cocok buat kebutuhan {detail} lo...", " Ringan dan praktis, gampang dibawa kemana-mana."),
        ("Baru nemu yang ini buat {detail}...", " Kualitasnya nggak kalah sama brand mahal."),
        ("Untuk {detail}, yang ini banyak yang suka...", " Sekarang lagi ada promo juga, worth it dicoba."),
        ("Mending coba yang ini buat {detail}...", " Harganya masuk akal, kualitasnya oke."),
    ]
    
    # Pick template based on index
    tmpl = templates[idx % len(templates)]
    detail = details[0] if details else 'produk yang bagus'
    
    comment = f"{tmpl[0].format(detail=detail)}{tmpl[1]} Lagi ada promo menarik, bisa dicek langsung di sini ya, semoga membantu: {link}"
    
    return comment, ""

# Filter eligible posts
eligible = []
for p in pool:
    if p.get('lang') != 'id':
        continue
    if p['url'] in replied:
        continue
    if is_skip_post(p.get('text', '')):
        continue
    eligible.append(p)

print(f"Eligible ID posts: {len(eligible)}")

# Shuffle for variety
random.seed()
random.shuffle(eligible)

# Select 12 candidates
selected = eligible[:12]

# Build comments_new.json
comments = []
exclude_ids = []

for idx, post in enumerate(selected):
    url = post['url']
    author = post['author']
    text = post['text']
    
    # Find relevant product
    offer = find_relevant_product(text, exclude_ids)
    
    if not offer:
        continue
    
    exclude_ids.append(offer['offerId'])
    
    # Generate comment
    comment, extra_comment = generate_comment(post, offer, idx)
    
    # Get image path
    image_path = get_image_path(offer['offerId'])
    
    # Build item
    item = {
        'url': url,
        'author': author,
        'comment': comment,
        'lang': 'id',
        'media_path': image_path
    }
    
    # Add extra if needed (will be handled at posting time)
    if extra_comment:
        item['extra_comment'] = extra_comment
    
    comments.append(item)
    print(f"  [{idx+1}] @{author}: {text[:50]}...")
    print(f"      -> {comment[:80]}...")
    print(f"      Product: {offer['name'][:40]}...")

# Write output
with open(BOT / 'comments_new.json', 'w', encoding='utf-8') as f:
    json.dump(comments, f, ensure_ascii=False, indent=1)

print(f"\nWrote {len(comments)} comments to comments_new.json")
print(f"Used {len(exclude_ids)} unique products")
