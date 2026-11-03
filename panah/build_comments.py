#!/usr/bin/env python3
"""Build comments_new.json for Panah Threads bot refill."""
import json
import os
from pathlib import Path

BOT = Path(__file__).resolve().parent

# Load catalog
with open(BOT / 'catalog/catalog.json') as f:
    catalog = json.load(f)
offers = catalog.get('offers', [])

# Load pool
with open(BOT / 'pool_ready.json') as f:
    pool = json.load(f)

# Load replied URLs to avoid duplicates
replied = set()
try:
    with open(BOT / 'replied_urls.json') as f:
        replied = set(json.load(f))
except:
    pass

# Skip keywords for filtering
SKIP_KW = [
    'korupsi', 'prabowo', 'pilkada', 'dpr', 'politik', 'curang', 'selingkuh',
    'pacar', 'mantan', 'breakup', 'penghasilan', 'cuma', 'modal', 'bisnis online',
    'shopee affiliate', 'cancer', 'sakit', 'penyakit', 'rawatan', 'berlepas',
    'china', 'hospital', 'rumah sakit', 'demo', 'protes', 'gubernur', 'wali kota',
    'bupati', 'presiden', 'coblos', 'pajak rakyat', 'hancur', 'maga', 'trump',
    'midterms', 'election', 'political'
]

def is_skip_post(text):
    text_lower = text.lower()
    return any(kw in text_lower for kw in SKIP_KW)

def find_relevant_product(post_text, exclude_ids=None):
    """Find best matching product from catalog for post topic."""
    exclude_ids = exclude_ids or []
    text_lower = post_text.lower()
    
    # Category matching
    matches = []
    for o in offers:
        if o['offerId'] in exclude_ids:
            continue
        name = o['name'].lower()
        # Check relevance
        score = 0
        if 'mainan' in text_lower and ('mainan' in name or 'toy' in name or 'anak' in name):
            score += 10
        if 'makeup' in text_lower or 'perawatan' in text_lower or 'kulit' in text_lower:
            if any(k in name for k in ['lip', 'parfum', 'cream', 'makeup', 'beauty', 'skincare']):
                score += 10
        if 'sepatu' in text_lower or 'sandal' in text_lower:
            if any(k in name for k in ['sepatu', 'sandal', 'shoe']):
                score += 10
        if 'rayon' in text_lower or 'one set' in text_lower:
            if 'rayon' in name:
                score += 10
        if 'softlens' in text_lower or 'lens' in text_lower:
            if 'softlens' in name or 'lens' in name:
                score += 10
        if 'parfum' in text_lower:
            if 'parfum' in name or 'perfume' in name or 'wangi' in name:
                score += 10
        if 'tumbler' in text_lower or 'botol' in text_lower:
            if 'tumbler' in name or 'botol' in name:
                score += 10
        if 'minuman' in text_lower or 'coffee' in text_lower or 'kopi' in text_lower:
            if any(k in name for k in ['kopi', 'coffee', 'latte', 'minuman']):
                score += 10
        if 'buku' in text_lower or 'baca' in text_lower:
            if 'buku' in name:
                score += 10
        if 'tas' in text_lower or 'bag' in text_lower:
            if 'tas' in name or 'bag' in name:
                score += 10
        
        # Generic fallback
        if score == 0:
            if any(k in name for k in ['gula', 'sabun', 'tisu', 'parfum', 'hijab', 'kulot']):
                score = 1
        
        if score > 0:
            matches.append((score, o['offerId'], o))
    
    if not matches:
        # Fallback: pick a popular generic item
        for o in offers:
            if o['offerId'] not in exclude_ids:
                name = o['name'].lower()
                if any(k in name for k in ['parfum', 'hijab', 'gula', 'sabun']):
                    return o
        return offers[0] if offers else None
    
    matches.sort(key=lambda x: x[0], reverse=True)
    return matches[0][2]

def get_image_path(offer_id):
    """Get image path for offer."""
    img_dir = BOT / 'catalog' / 'images' / offer_id
    if img_dir.exists():
        files = list(img_dir.glob('*.jpg')) + list(img_dir.glob('*.png'))
        if files:
            return str(files[0])
    return ""

def generate_comment(post, offer, idx):
    """Generate Panah persona comment for post + offer."""
    text = post['text']
    offer_name = offer['name']
    link = offer['link']
    
    # Extract topic keywords for reaction
    text_lower = text.lower()
    
    # Identify post topic
    if 'mainan' in text_lower or 'anak' in text_lower:
        topic = 'mainan anak'
    elif 'makeup' in text_lower or 'perawatan' in text_lower:
        topic = 'makeup'
    elif 'sepatu' in text_lower or 'sandal' in text_lower:
        topic = 'sepatu'
    elif 'rayon' in text_lower or 'one set' in text_lower:
        topic = 'one set rayon'
    elif 'softlens' in text_lower:
        topic = 'softlens'
    elif 'parfum' in text_lower:
        topic = 'parfum'
    elif 'tumbler' in text_lower or 'botol' in text_lower:
        topic = 'tumbler'
    elif 'buku' in text_lower:
        topic = 'buku'
    elif 'tas' in text_lower:
        topic = 'tas'
    else:
        topic = 'produk'
    
    # Generate varied openers (anti-generic)
    openers = [
        f"Nih, kalau lagi cari {topic} yang worth it...",
        f"Kalau lagi butuh {topic}, ini beberapa rekomendasi oke:",
        f" lagi nyari {topic}? Coba cek yang ini dulu:",
        f" buat {topic}, ini ada yang lagi promo menarik:",
        f" untuk kebutuhan {topic}, yang ini banyak yang suka:",
    ]
    
    # Generate benefit statements
    benefits = [
        f" Bahannya adem dan nyaman dipakai sehari-hari.",
        f" Banyak yang review kualitasnya oke banget.",
        f" Worth it buat daily use, ringan dan praktis.",
        f" Desainnya kece, cocok buat daily activity.",
        f" Reviewnya bagus-bagus, banyak yang repurchase.",
    ]
    
    # Pick based on index
    opener = openers[idx % len(openers)]
    benefit = benefits[idx % len(benefits)]
    
    # Build comment
    comment = f"{opener}{benefit} Sekarang lagi ada promo juga, bisa dicek langsung di sini ya, semoga membantu: {link}"
    
    return comment

# Filter eligible posts
eligible = []
for p in pool:
    if p['lang'] != 'id':
        continue
    if p['url'] in replied:
        continue
    if is_skip_post(p['text']):
        continue
    eligible.append(p)

print(f"Eligible ID posts: {len(eligible)}")

# Select 12 diverse candidates
# First pass: find posts with clear product relevance
high_priority = []
for p in eligible:
    text = p['text']
    if any(k in text.lower() for k in ['mainan', 'anak', 'makeup', 'parfum', 'sepatu', 'sandal', 'rayon', 'one set', 'softlens', 'tumbler', 'buku', 'tas']):
        high_priority.append(p)

print(f"High priority posts: {len(high_priority)}")

# Select from high priority first
selected = []
for p in high_priority[:12]:
    selected.append(p)

# Fill remaining if needed
for p in eligible:
    if len(selected) >= 12:
        break
    if p not in selected:
        selected.append(p)

print(f"Selected: {len(selected)}")

# Build comments_new.json
comments = []
exclude_ids = []

for idx, post in enumerate(selected):
    # Find relevant product
    offer = find_relevant_product(post['text'], exclude_ids)
    
    if not offer:
        continue
    
    # Track used offer IDs to avoid duplicates
    exclude_ids.append(offer['offerId'])
    
    comment = generate_comment(post, offer, idx)
    image_path = get_image_path(offer['offerId'])
    
    # Note: fetch_top_reply.py requires cloakbrowser which is not available
    # So we write main comment only, no extra_comment
    # The daemon will handle extra at posting time if thread is busy
    
    item = {
        'url': post['url'],
        'author': post['author'],
        'comment': comment,
        'lang': 'id',
        'media_path': image_path
    }
    
    comments.append(item)

# Write output
with open(BOT / 'comments_new.json', 'w', encoding='utf-8') as f:
    json.dump(comments, f, ensure_ascii=False, indent=1)

print(f"Wrote {len(comments)} comments to comments_new.json")

# Show preview
for i, c in enumerate(comments[:5]):
    print(f"\n--- Item {i+1} ---")
    print(f"URL: {c['url']}")
    print(f"Comment: {c['comment'][:120]}...")
