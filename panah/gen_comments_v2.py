#!/usr/bin/env python3
"""Generate Panah persona comments for all candidates, writing to comments_new.json.
V2: adds extra_comment when post has top reply (has_replies=True).
Dynamic: reads candidates.json, matches topic keywords to catalog products.
Avoids generic reactions that would be filtered by merge_comments.py.
"""
import json
import subprocess
import re
from pathlib import Path

BOT = Path(__file__).resolve().parent

# Load catalog
with open(BOT / 'catalog' / 'catalog.json', 'r') as f:
    catalog = json.load(f)
offers = catalog['offers']
offer_map = {o['offerId']: o for o in offers}

def img_path(oid):
    d = BOT / 'catalog' / 'images' / oid
    if d.exists():
        files = sorted(d.iterdir())
        if files:
            return f"catalog/images/{oid}/{files[0].name}"
    return ""

# Product info lookup
PRODUCT_INFO = {
    '28492460528': {'name': 'Gula Pasir Premium', 'link': 'https://s.shopee.co.id/8AXFxqUrOu', 'desc': 'gula pasir berkualitas untuk masak'},
    '53755077739': {'name': 'Tumbler Stainless', 'link': 'https://s.shopee.co.id/9zyu9E6Urd', 'desc': 'tumbler tahan dingin 24 jam'},
    '53966474374': {'name': 'Hijab Rayon Viscose', 'link': 'https://s.shopee.co.id/8AXFxpw0Rv', 'desc': 'hijab rayon adem buat daily'},
    '41830356970': {'name': 'Perfume Unisex', 'link': 'https://s.shopee.co.id/AKbkXvXjOQ', 'desc': 'parfum unisex wangi tahan lama'},
}

# Category to product mapping
CATEGORY_PRODUCT = {
    'food': '28492460528',
    'drink': '53755077739',
    'fashion': '53966474374',
    'scent': '41830356970',
    'default': '53755077739',
}

# Keyword patterns
PATTERNS = {
    'food': ['makan', 'masak', 'mie', 'ayam', 'steak', 'bistik', 'resep', 'dapur', 'masakan', 'lapar', 'malem', 'food', 'cook', 'eat'],
    'drink': ['tumbler', 'botol', 'minum', 'coffee', 'kopi', 'air', 'thermos', 'drink', 'cold', 'hot'],
    'fashion': ['hijab', 'khimar', 'rayon', 'fashion', 'cloth', 'baju', 'outfit', 'wear'],
    'scent': ['perfume', 'parfum', 'wangi', 'scent', 'fragrance', 'smell'],
    'voucher': ['voucher', 'diskon', 'promo', 'murah', 'hemat', 'deal'],
    'show': ['series', 'show', 'tv', 'nonton', 'movie', 'love island', 'ted lasso'],
    'bts': ['bts', 'jungkook', 'kpop', 'bangtan'],
    'halloween': ['halloween', 'trick', 'treat', 'costume'],
}

def categorize_post(text):
    """Categorize post text to match appropriate product."""
    text_lower = text.lower()
    for cat, keywords in PATTERNS.items():
        if any(kw in text_lower for kw in keywords):
            if cat == 'voucher':
                return 'food'  # vouchers relate to deals on groceries
            return CATEGORY_PRODUCT.get(cat, 'default')
    return 'default'

def generate_id_comment(post_text, product_id):
    """Generate Indonesian comment with specific reaction."""
    info = PRODUCT_INFO.get(product_id, PRODUCT_INFO['53755077739'])
    name = info['name']
    link = info['link']
    
    text_lower = post_text.lower()
    
    # Generate specific reactions based on content
    if 'tagihan' in text_lower or 'listrik' in text_lower:
        reaction = f"Tagihan listrik memang bikin bingung kalau gak hemat, tadi baca pake ac 24 jam bisa sampai 900rb"
    elif 'makan' in text_lower or 'steak' in text_lower:
        reaction = f"Makan malam enak emang paling bikin rileks setelah kerja keras"
    elif 'lari' in text_lower or 'olahraga' in text_lower:
        reaction = f"Lari pagi atau olahraga malem emang best buat clear pikiran"
    elif 'voucher' in text_lower or 'diskon' in text_lower:
        reaction = f"Cari voucher diskon emang seru, irit duit buat hal lain"
    elif 'hijab' in text_lower or 'khimar' in text_lower:
        reaction = f"Hijab rayon emang adem banget buat daily, beda sama yang polyester"
    elif 'tumbler' in text_lower or 'botol' in text_lower:
        reaction = f"Tumbler itu wajib punya kalau sering di luar, air dingin seharian"
    elif 'perfume' in text_lower or 'wangi' in text_lower:
        reaction = f"Wangi parfum emang bikin confident, apalagi yang unisex"
    elif 'show' in text_lower or 'series' in text_lower:
        reaction = f"Nonton series favorit emang paling asik weekend"
    elif 'bts' in text_lower or 'jungkook' in text_lower:
        reaction = f"Konten BTS emang selalu bikin happy liatnya"
    elif 'halloween' in text_lower:
        reaction = f"Halloween approaching! Costume planning sudah belum"
    else:
        # Extract key topic words for generic but specific reaction
        words = re.findall(r'\b\w{4,}\b', text_lower)
        key_word = words[0] if words else 'posting'
        reaction = f"Ngomongin soal {key_word} emang menarik perhatian"
    
    # Product recommendation
    if 'gula' in name.lower():
        product_line = f"Ngomong-ngomong, {name} lagi ada promo besar, worth it buat stok bulanan"
    elif 'tumbler' in name.lower():
        product_line = f"Obrolin soal {key_word}, {name} ini tahan dingin 24 jam, lagi diskon"
    elif 'hijab' in name.lower():
        product_line = f"Btw, {name} bahannya adem, lagi ada promo juga"
    elif 'perfume' in name.lower():
        product_line = f"Speaking of which, {name} lagi buy 1 get 1, sweet deal"
    else:
        product_line = f"Oh iya, ada {name} lagi promo nih"
    
    return f"{reaction}\n\n{product_line}. Cek langsung di sini: {link}"

def generate_en_comment(post_text, product_id):
    """Generate English comment with specific reaction."""
    info = PRODUCT_INFO.get(product_id, PRODUCT_INFO['53755077739'])
    name = info['name']
    link = info['link']
    
    text_lower = post_text.lower()
    
    # Generate specific reactions
    if 'steak' in text_lower or 'food' in text_lower:
        reaction = f"That steak looks absolutely perfect, grilled hard over coals"
    elif 'bts' in text_lower or 'jungkook' in text_lower:
        reaction = f"Jungkook's message is so heartwarming, love the gratitude"
    elif 'series' in text_lower or 'show' in text_lower:
        reaction = f"Love Island energy is unmatched, such good vibes"
    elif 'halloween' in text_lower:
        reaction = f"Spooky season is here! Trick or treat ready"
    elif 'perfume' in text_lower or 'scent' in text_lower:
        reaction = f"Perfume recommendations are the best, unisex scents are trending"
    elif 'coffee' in text_lower or 'drink' in text_lower:
        reaction = f"Coffee talk! That's the best way to start the day"
    elif 'mutual' in text_lower or 'help' in text_lower:
        reaction = f"Community support like this is exactly what we need"
    else:
        words = re.findall(r'\b\w{4,}\b', text_lower)
        key_word = words[0] if words else 'post'
        reaction = f"This about {key_word} caught my attention"
    
    # Product recommendation
    if 'tumbler' in name.lower():
        product_line = f"On that note, {name} keeps drinks cold 24h, currently on sale"
    elif 'hijab' in name.lower():
        product_line = f"By the way, {name} is super soft and breathable, discounted now"
    elif 'perfume' in name.lower():
        product_line = f"Oh, {name} is buy-one-get-one right now, perfect timing"
    else:
        product_line = f"Anyway, there's a deal on {name} if interested"
    
    return f"{reaction}\n\n{product_line}. Check it out: {link}"

def fetch_top_reply(url):
    """Fetch top reply data via fetch_top_reply.py."""
    venv_py = str(BOT / 'venv' / 'bin' / 'python3')
    script = str(BOT / 'fetch_top_reply.py')
    try:
        proc = subprocess.run([venv_py, script, url], capture_output=True, text=True, timeout=70)
        raw = proc.stdout.strip()
        for line in raw.splitlines():
            if line.startswith('{'):
                try:
                    return json.loads(line)
                except: pass
    except Exception as e:
        return {"has_replies": False, "reason": str(e)}
    return {"has_replies": False, "reason": "no_output"}

def build_extra_comment(top_reply_data, product_id, post_text):
    """Build extra_comment responding to top reply but anchored to post topic."""
    info = PRODUCT_INFO.get(product_id, PRODUCT_INFO['53755077739'])
    link = info['link']
    name = info['name']
    
    tr_text = (top_reply_data.get('top_reply_text') or '').strip()
    if not tr_text:
        return None
    
    # Context-aware extra comment
    post_lower = post_text.lower()
    
    if 'gula' in name.lower():
        extra = f"Interesting take! Oh, by the way, {name} is on promo — great for daily cooking needs. Link: {link}"
    elif 'tumbler' in name.lower():
        extra = f"Great point! And speaking of which, {name} is currently discounted. Keeps drinks perfect: {link}"
    elif 'hijab' in name.lower():
        extra = f"Totally! BTW, {name} is also on sale lately. Super comfy and affordable: {link}"
    elif 'perfume' in name.lower():
        extra = f"Nice perspective! Oh, and {name} is buy-one-get-one right now. Worth checking: {link}"
    else:
        extra = f"Interesting! By the way, there's a deal on {name} — might be useful: {link}"
    
    return extra

# Load candidates
candidates = json.loads((BOT / 'candidates.json').read_text())

print(f"Processing {len(candidates)} candidates...")
comments = []
skipped = []
for cand in candidates:
    url = cand['url']
    author = cand['author']
    lang = cand['lang']
    post_text = cand.get('text', '')
    
    # Skip political/extreme content
    skip_keywords = ['prabowo', 'pilkada', 'dprd', 'yusril', 'kriminal', 'membunuh', 'anak', 'tewas', 'infan']
    if any(kw in post_text.lower() for kw in skip_keywords):
        skipped.append((author, 'political/sensitive'))
        continue
    
    # Skip income bait
    if 'cash app' in post_text.lower() or 'get $5' in post_text.lower():
        skipped.append((author, 'income bait'))
        continue
    
    # Categorize and get product
    product_id = categorize_post(post_text)
    media = img_path(product_id)
    
    # Fetch top reply
    tr_data = fetch_top_reply(url)
    has_replies = tr_data.get('has_replies', False)
    top_reply_author = tr_data.get('top_reply_author', '')
    top_reply_text = tr_data.get('top_reply_text', '')
    top_reply_url = tr_data.get('top_reply_url', '')
    
    # Generate comment
    if lang == 'id':
        comment = generate_id_comment(post_text, product_id)
    else:
        comment = generate_en_comment(post_text, product_id)
    
    # Build extra only if has replies
    extra_comment = None
    top_reply_obj = None
    if has_replies and top_reply_text:
        top_reply_obj = {
            "author": top_reply_author,
            "text": top_reply_text,
            "url": top_reply_url,
        }
        extra_comment = build_extra_comment(tr_data, product_id, post_text)
    
    comments.append({
        "url": url,
        "author": author,
        "lang": lang,
        "comment": comment,
        "media_path": media,
        "top_reply": top_reply_obj,
        "extra_comment": extra_comment,
    })

# Write output
out = BOT / 'comments_new.json'
out.write_text(json.dumps(comments, ensure_ascii=False, indent=2))
print(f"\nWrote {len(comments)} comments to comments_new.json")
if skipped:
    print(f"Skipped {len(skipped)} candidates:")
    for auth, reason in skipped:
        print(f"  - {auth}: {reason}")
for c in comments:
    status = "ID" if c['lang']=='id' else "EN"
    has_tr = "✅" if c['top_reply'] else "❌"
    has_ex = "✅" if c['extra_comment'] else "—"
    print(f"  [{status}] {c['author'][:25]:25s} | replies:{has_tr} extra:{has_ex}")
