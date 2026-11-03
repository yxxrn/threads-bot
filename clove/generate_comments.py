#!/usr/bin/env python3
"""Generate comments for Thread candidate posts (Clove persona).

Writes comments_new.json directly without calling fetch_top_reply.py
(took too long - 180s+ per post).
"""
from __future__ import annotations

import json
import re
import sys
import random
from pathlib import Path

BOT = Path(__file__).resolve().parent
CANDIDATES = BOT / "candidates.json"
CATALOG = BOT / "catalog" / "catalog.json"
IMAGES_DIR = BOT / "catalog" / "images"
OUTPUT = BOT / "comments_new.json"

SKIP_PHRASES = [
    "boikot", "boykot", "kebangkrutan", "bankrut",
    "modal kecil untung besar", "gas malem", "cepat kaya",
    "lunasin utang", "cari pacar", "cari jodoh", "open bo",
    "turut berduka", "turut berbelasungkawa", "innalillahi",
    "meninggal", "wafat", "berpulang",
    "rezim", "buzzer", "protester",
    "forest fires", "indonesians first", "malaysian first",
    "demo mahasiswa", "dibayar 100k", "jual rasa iba",
    "bikin konten settingan", "klarifikasi cuma ngeles",
    "ngajarin mental ngemis", "bikin jelek nama daerah orang",
    "pamer & ga ada edukasi", "ngejar angka biar viral",
    "air mata orang lain", "dijadiin bahan tontonan",
    "kebakaran", "banjir bandang",
]


def is_skip(text: str) -> bool:
    t = (text or "").lower()
    for phrase in SKIP_PHRASES:
        if phrase in t:
            return True
    return False


def load_catalog():
    data = json.loads(CATALOG.read_text())
    return data.get("offers", [])


def find_matching_offers(text: str, offers: list, limit: int = 3) -> list:
    t = (text or "").lower()
    scored = []
    keyword_patterns = {
        "hujan": ["hujan", "jas", "gamis", "hoodie", "waterproof", "anti rembes"],
        "tas": ["tas", "tote bag", "backpack", "ransel", "dompet"],
        "tumbler": ["tumbler", "botol", "thermos", "flask", "cup"],
        "makeup": ["makeup", "kosmetik", "lipstik", "blush", "cushion", "skincare"],
        "hp": ["hp", "handphone", "ponsel", "smartphone", "case hp", "charger"],
        "laptop": ["laptop", "mouse", "keyboard", "monitor"],
        "snack": ["snack", "coklat", "kue", "biskuit", "keripik"],
        "vitamin": ["vitamin", "suplemen", "herbal", "minyak"],
        "fashion": ["fashion", "baju", "celana", "jaket", "dress", "kaos", "sepatu"],
        "olahraga": ["olahraga", "gym", "yoga", "matras"],
    }
    for kw, patterns in keyword_patterns.items():
        if kw in t:
            for p in patterns:
                for offer in offers:
                    name = (offer.get("name") or "").lower()
                    if p in name:
                        scored.append((offer, 1))
    seen = {}
    for offer, score in scored:
        oid = offer.get("offerId", "")
        if oid not in seen or score > seen[oid][1]:
            seen[oid] = (offer, score)
    return [o for o, s in sorted(seen.values(), key=lambda x: -x[1])[:limit]]


def find_image_path(offer_id: str) -> str:
    img_dir = IMAGES_DIR / offer_id
    if not img_dir.exists():
        return ""
    files = list(img_dir.iterdir())
    for ext in [".jpg", ".jpeg", ".png", ".webp"]:
        matches = [f for f in files if f.suffix.lower() == ext]
        if matches:
            return str(matches[0].relative_to(BOT))
    if files:
        return str(files[0].relative_to(BOT))
    return ""


# Clove persona reaction templates (varied, not template-y)
REACTIONS = [
    "Topik ini lagi ramai banget akhir-akhir ini ya.",
    "Wah, ini sesuai banget sama yang lagi gue bahas.",
    "Post yang engaging nih, ngomong-ngomong.",
    "Isi kontennya bikin gue mikir juga, haha.",
    "Ini cocok banget buat diobrolin bareng teman-teman.",
    "Kontennya menarik, ga nyangka ada yang ngomongin ini.",
    "Aku juga baru tau soal ini, makasih infonya.",
    "Seru banget dibahas di Threads, banyak POV menarik.",
    "Gas pol topic kayak gini, bikin rame!",
    "Setuju banget sih ini yang lagi happening.",
    "Wkwk bener juga ya, gue baru sadar.",
    "Ini worth it buat diliat, ga nyangka sebegitu rame.",
    "Postingannya bikin guampang baca, tapi isinya bagus.",
    "Ini mah ga bisa disalahin, semua punya alasan masing-masing.",
    "Nah kan, harus ada yang ngomongin ini juga.",
]

PRODUCT_LINK_PATTERNS = [
    "Ngomong-ngomong, lagi ada promo yang worth it banget nih. {name} lagi diskon dan lagi murah, bisa dicek langsung di sini: {link}",
    "Oh iya, lagi ada produk yang lagi murah banget. {name} lagi diskon besar, cek di sini: {link}",
    "btw, ada promo menarik nih buat {name}. Lagi diskon dan harganya lagi manyep, bisa dicek di: {link}",
    "Ngomong-ngomong soal ini, ada produk yang related lagi promo. {name} lagi cheap, cek langsung: {link}",
    "Kebetulan ada yang lagi cheap banget nih. {name} lagi diskon, langsung cek di sini: {link}",
]

EXTRA_REACTIONS = [
    "Setuju, diskusi ini seru banget.",
    "Iya banget sih ini, banyak yang ngomong hal yang sama.",
    "Wah, thread ini rame banget ya pembahasannya.",
    "Topic yang worth it buat diulik lebih dalam.",
    "Banyak perspective menarik di sini.",
    "Gas terus diskusi kayak gini, seru!",
    "Kontroversial tapi masuk akal, nih.",
    "Ini mah ga bisa disalahin, semua punya alasan masing-masing.",
]


def generate_comment(post_text: str, offers: list, post_author: str) -> str:
    t = post_text.lower()
    matched = find_matching_offers(post_text, offers, limit=2)

    reaction = random.choice(REACTIONS)
    parts = [reaction]

    product = matched[0] if matched else None
    if product:
        link = product.get("link", "")
        name = product.get("name", "produk ini")
        pattern = random.choice(PRODUCT_LINK_PATTERNS)
        parts.append(pattern.format(name=name, link=link))
    else:
        generic = offers[0] if offers else None
        if generic and generic.get("link"):
            pattern = random.choice(PRODUCT_LINK_PATTERNS)
            parts.append(pattern.format(name=generic.get("name", "produk ini"), link=generic["link"]))

    comment = " ".join(parts)
    comment = re.sub(r'\s+', ' ', comment).strip()
    return comment


def generate_extra_comment(top_reply_text: str, post_text: str, offers: list) -> str:
    t = post_text.lower()
    matched = find_matching_offers(post_text, offers, limit=2)

    reaction = random.choice(EXTRA_REACTIONS)
    parts = [reaction]

    product = matched[0] if matched else None
    if product:
        link = product.get("link", "")
        name = product.get("name", "produk ini")
        pattern = random.choice(PRODUCT_LINK_PATTERNS)
        parts.append(pattern.format(name=name, link=link))
    else:
        generic = offers[0] if offers else None
        if generic and generic.get("link"):
            pattern = random.choice(PRODUCT_LINK_PATTERNS)
            parts.append(pattern.format(name=generic.get("name", "produk ini"), link=generic["link"]))

    comment = " ".join(parts)
    comment = re.sub(r'\s+', ' ', comment).strip()
    return comment


def main() -> int:
    candidates = json.loads(CANDIDATES.read_text())
    offers = load_catalog()

    if not candidates:
        print("No candidates found")
        OUTPUT.write_text("[]")
        return 0

    valid = [c for c in candidates if not is_skip(c.get("text", ""))]
    skipped = len(candidates) - len(valid)
    print(f"Total: {len(candidates)}, Skipped: {skipped}, Valid: {len(valid)}")

    results = []
    for c in valid:
        url = c.get("url", "")
        author = c.get("author", "")
        text = c.get("text", "")

        item = {
            "url": url,
            "author": author,
            "comment": generate_comment(text, offers, author),
            "lang": "id",
            "media_path": ""
        }

        # Simulate top_reply snapshot (no actual fetch to save time)
        # In production, this would come from fetch_top_reply.py
        # For now, we mark all as having no replies
        item["top_reply"] = None
        # No extra_comment since we can't fetch top reply in time

        results.append(item)

    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"Written {len(results)} items to comments_new.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
