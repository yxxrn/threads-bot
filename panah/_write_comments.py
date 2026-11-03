import json
import os
import random

# Load catalog
with open('/home/agentuser/threads-bot-panah/catalog/catalog.json') as f:
    catalog = json.load(f)

offers = catalog['offers']

# Load candidates
with open('/home/agentuser/threads-bot-panah/candidates.json') as f:
    candidates = json.load(f)

# Top reply data from fetch_top_reply
top_replies = {
    'https://www.threads.net/@finurika/post/DDnGZJhR0iC': {'has_replies': False, 'reply_count': 0},
    'https://www.threads.net/@rizalhadizan/post/DDnG8zYRGqX': {'has_replies': False, 'reply_count': 0},
    'https://www.threads.net/@skapuq/post/DfJ8HnPk_uH': {'has_replies': True, 'reply_count': 10, 'top_reply_author': 'skapuq', 'top_reply_text': 'Prajurit Terseret Korupsi BNPB, KPK Menanti Jawaban TNI', 'top_reply_url': 'https://www.threads.com/@skapuq/post/DfJ8LkFk2SF'},
    'https://www.threads.net/@kasyoi/post/DfKVFn7kyl8': {'has_replies': True, 'reply_count': 1, 'top_reply_author': 'nadiasansuri', 'top_reply_text': 'Alhamdulliah mak saya baru berlepas ke china...', 'top_reply_url': 'https://www.threads.com/@nadiasansuri/post/DfKR8DGk1fg'},
    'https://www.threads.net/@manuprojectpro/post/DfKrzi2jMmb': {'has_replies': True, 'reply_count': 1, 'top_reply_author': 'inimedanbungg', 'top_reply_text': 'Giat penindakan pengendara sepeda motor knalpot brong...', 'top_reply_url': 'https://www.threads.com/@inimedanbungg/post/DfKstokH8zP'},
    'https://www.threads.net/@ffraaahhdina__/post/DfKqgrADxX7': {'has_replies': True, 'reply_count': 21, 'top_reply_author': 'haizadgaf', 'top_reply_text': 'Weh sama lah, dapat msj tu jugak...', 'top_reply_url': 'https://www.threads.com/@haizadgaf/post/DfKvVJhk6gR'},
    'https://www.threads.net/@doniecnn/post/DfKUbsSkywv': {'has_replies': True, 'reply_count': 60, 'top_reply_author': 'gockomo', 'top_reply_text': 'Is there anything he could do?... Trump corruption...', 'top_reply_url': 'https://www.threads.com/@gockomo/post/DfKjewzIAwu'},
    'https://www.threads.net/@ssssswasthere/post/DfKdiLFmZOT': {'has_replies': True, 'reply_count': 6, 'top_reply_author': 'ssssswasthere', 'top_reply_text': 'Kids club cantik, apatah lagi hotelnya...', 'top_reply_url': 'https://www.threads.com/@ssssswasthere/post/DfKjbw2mdod'},
    'https://www.threads.net/@miabellavita74/post/DfJ5ltNEfdJ': {'has_replies': True, 'reply_count': 17, 'top_reply_author': 'movecleanbali2', 'top_reply_text': 'Save it, in case you need it...', 'top_reply_url': 'https://www.threads.com/@movecleanbali2/post/DfKnKc9EzFx'},
    'https://www.threads.net/@naylaisyy/post/DfJkMb7k-Wu': {'has_replies': False, 'reply_count': 0},
    'https://www.threads.net/@fitry_anggrainy170797/post/DfJg6STHfjQ': {'has_replies': False, 'reply_count': 0},
    'https://www.threads.net/@bambangirawan911/post/DfJc7iojgLW': {'has_replies': False, 'reply_count': 0},
}

# Skip keywords
skip_keywords_id = ['korupsi', 'presiden', 'demo', 'polri', 'tndi', 'bnkb', 'nepotisme', 'suap', 'gratisan', 'buzzer', 'boikot']
skip_keywords_en = ['trump', 'maga', 'politics', 'election', 'corruption']

def is_skip(c):
    text = c['text'].lower()
    lang = c['lang']
    
    if lang == 'id':
        for kw in skip_keywords_id:
            if kw in text:
                return True, kw
    else:
        for kw in skip_keywords_en:
            if kw in text:
                return True, kw
    
    if any(w in text for w in ['curang', 'selingkuh', 'pacar', 'mantan', 'cheat']):
        return True, 'romance drama'
    
    if any(w in text for w in ['penghasilan', 'cuan', 'income', 'duit', 'duit cepat']):
        return True, 'income bait'
    
    return False, None

def find_product(c):
    text = c['text'].lower()
    lang = c['lang']
    
    relevant = []
    
    for o in offers:
        name = o['name'].lower()
        score = 0
        
        if lang == 'id':
            if 'motor' in text or 'evo' in text or 'knalpot' in text:
                if any(k in name for k in ['jas hujan', 'raincoat', 'helm', 'tas']):
                    score += 10
            if 'bali' in text or 'hotel' in text or 'travel' in text:
                if any(k in name for k in ['tumbler', 'botol', 'tas', 'ransel', 'travel']):
                    score += 8
            if 'musik' in text or 'lagu' in text or 'nyanyi' in text:
                if 'earphone' in name or 'headphone' in name:
                    score += 8
            if any(k in name for k in ['tas', 'rucksack', 'backpack']):
                score += 3
            if any(k in name for k in ['tumbler', 'botol minum', 'thermos']):
                score += 3
            if any(k in name for k in ['hijab', 'khimar', 'jilbab']):
                score += 3
        else:
            if any(k in name for k in ['tumbler', 'botol', 'thermos', 'tas', 'hijab']):
                score += 5
        
        if score > 0:
            relevant.append((score, o))
    
    if relevant:
        relevant.sort(key=lambda x: x[0], reverse=True)
        return relevant[0][1]
    
    return random.choice(offers[:20])

def write_comment(c, product, has_top_reply, top_reply_data):
    text = c['text']
    lang = c['lang']
    url = c['url']
    author = c['author']
    
    comment_parts = []
    
    # Main comment - natural reaction based on topic
    if lang == 'id':
        if 'motor' in text.lower() or 'evo' in text.lower() or 'knalpot' in text.lower():
            main = "Wah event motor seru juga nih! Buat yang suka touring atau racing, perlu perlengkapan lengkap ya. Nih kalau butuh jas hujan atau tas buat sembunyiin barang, lagi ada promo menarik, cek langsung di sini ya! 🏍️"
        elif 'bali' in text.lower() or 'hotel' in text.lower():
            main = "Bali emang selalu jadi favorit buat liburan! Udah ready belum perjalanannya? Oh iya, kalau mau bawa botol minum atau tas travel yang praktis, lagi diskon nih! Linknya di sini ya, semoga membantu ✨"
        elif 'musik' in text.lower() or 'lagu' in text.lower() or 'nyanyi' in text.lower():
            main = "Lagu bagus emang nggak bosen-dosen dengerinnya! ✨ Ngomong-ngomong, lagi ada promo produk menarik buat sehari-hari, cek langsung di sini ya!"
        elif 'hijab' in text.lower() or 'busana' in text.lower():
            main = "Model hijab yang bagus emang bikin penampilan makin oke! Ini nih yang lagi rame, bahannya adem dan worth it buat daily. Lagi ada promo juga, bisa dicek langsung di sini ya! 😊"
        else:
            main = "Wah menarik juga pembahasan ini! ✨ Oh iya, ngomong-ngomong ada produk menarik lagi promo, bisa dicek di sini ya!"
    else:
        main = "Interesting post! ✨ By the way, there's a great product on promo right now, check it out here!"
    
    comment_parts.append(main)
    
    # Extra comment if has replies
    extra = None
    if has_top_reply and top_reply_data:
        if lang == 'id':
            extra = "Semoga info ini bermanfaat! Oh iya, buat yang cari perlengkapan sehari-hari, lagi ada promo menarik nih, cek linknya di sini ya! 😊"
        else:
            extra = "Hope this helps! Also, if you need something useful, there's a promo going on. Check it out here!"
    
    # Get product link and image
    link = product['link']
    # LINK-ALL guard (2026-11-01): link must be inline in the text,
    # never only in the separate product_link field (poster ignores it).
    if "http" not in main:
        main = main + f" Link: {link}"
    if extra and "http" not in extra:
        extra = extra + f" Link: {link}"
    offer_id = product['offerId']
    img_path = ''
    
    images_dir = '/home/agentuser/threads-bot-panah/catalog/images/'
    folder = os.path.join(images_dir, offer_id)
    if os.path.isdir(folder):
        for f in os.listdir(folder):
            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                img_path = f'/home/agentuser/threads-bot-panah/catalog/images/{offer_id}/{f}'
                break
    
    result = {
        'url': url,
        'author': author,
        'comment': main,
        'lang': lang,
        'media_path': img_path,
        'product_link': link
    }
    
    if extra:
        result['extra_comment'] = extra
        result['top_reply_snapshot'] = {
            'author': top_reply_data.get('top_reply_author', ''),
            'text': top_reply_data.get('top_reply_text', ''),
            'url': top_reply_data.get('top_reply_url', '')
        }
    
    return result

# Process candidates
results = []
skipped_list = []

for c in candidates:
    should_skip, reason = is_skip(c)
    if should_skip:
        skipped_list.append({'url': c['url'], 'author': c['author'], 'reason': reason})
        continue
    
    product = find_product(c)
    has_reply = top_replies.get(c['url'], {}).get('has_replies', False)
    reply_data = top_replies.get(c['url'], {})
    
    comment = write_comment(c, product, has_reply, reply_data)
    _seen = {r['comment'] for r in results}
    if comment['comment'] in _seen:
        continue  # dedup: never queue identical texts (2026-11-01)
    results.append(comment)

# Save results
with open('/home/agentuser/threads-bot-panah/comments_new.json', 'w') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"Written {len(results)} comments to comments_new.json")
print(f"Skipped {len(skipped_list)} candidates:")
for s in skipped_list:
    print(f"  - {s['author']}: {s['reason']}")
