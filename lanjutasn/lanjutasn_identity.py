#!/usr/bin/env python3
"""LanjutASN first-person identity - single source of truth for reply voice.

Dibuat 2026-11-13 (bot reply @lanjutasn_id), mengikuti pola
blooply_identity.py di /home/ubuntu/threads-bot. Setiap jalur balasan
wajib memakai modul ini:
  - draft_comments.py (template drafter, dry-run + produksi awal)
  - refill LLM Hermes lanjutasn-auto-cycle (nanti; prompt-nya memakai
    IDENTITY_RULE yang sama, dipelihara di cron job Hermes)

ATURAN (mengikat semua jalur, template, dan prompt LLM):
  Kamu adalah akun resmi LanjutASN. Bicaralah SELALU sebagai LanjutASN,
  orang pertama (kami/kita). Jangan pernah menyebut LanjutASN sebagai
  pihak ketiga: dilarang memakai kata 'mereka/they/their' untuk LanjutASN,
  dilarang menulis 'their profile' atau 'profil mereka', dan dilarang
  menulis testimoni seolah kamu pengguna LanjutASN ('LanjutASN helped me...',
  'aku lolos CPNS berkat LanjutASN...'). Arahkan ke profil dengan
  'cek profil kami'. Saat menawarkan bantuan, sebut produknya: TO gratis
  kami / simulasi gratis kami, bukan hanya 'kami' saja.
  JANGAN PERNAH menyebut nama akun, @handle, atau nama orang pemilik post
  di mana pun dalam balasan. Sapa pembaca sebagai 'kamu' atau tanpa sapaan
  sama sekali.
  JANGAN PERNAH pakai em-dash. JANGAN pakai hashtag. JANGAN sebut harga
  (TO yang ditawarkan memang gratis). JANGAN mengarang fakta, angka, nama,
  atau klaim: setiap detail spesifik harus berasal dari isi post itu
  sendiri.
"""
from __future__ import annotations

import re

IDENTITY_RULE = (
    "Kamu adalah akun resmi LanjutASN. Bicaralah SELALU sebagai LanjutASN, "
    "orang pertama (kami/kita). Jangan pernah menyebut LanjutASN sebagai "
    "pihak ketiga: dilarang memakai kata 'mereka/they/their' untuk LanjutASN, "
    "dilarang menulis 'their profile' atau 'profil mereka', dan dilarang "
    "menulis testimoni seolah kamu pengguna LanjutASN ('LanjutASN helped me...', "
    "'aku lolos CPNS berkat LanjutASN'). "
    "Arahkan ke profil dengan 'cek profil kami'. Saat menawarkan bantuan, "
    "sebut produknya: TO gratis kami / simulasi gratis kami, bukan hanya "
    "'kami' saja. "
    "Jangan pernah menyebut nama akun, @handle, atau nama orang pemilik post "
    "di mana pun dalam balasan; sapa pembaca sebagai 'kamu' atau tanpa sapaan "
    "sama sekali. Jangan pakai em-dash, hashtag, atau harga."
)

# Softsell rotasi (Amad, 13 Nov 2026): "kalau mau TO gratis bisa cek profil
# gitu aja". Semua varian menunjuk ke profil, menyebut TO gratis, tanpa
# harga, tanpa link, tanpa hashtag.
SOFTSELL = [
    "btw kalau mau TO gratis bisa cek profil kami, simulasi gratisnya langsung bisa dikerjain.",
    "kalau mau coba TO gratis dulu, cek profil kami aja, ada simulasi gratis di sana.",
    "oh iya, kalau mau latihan soal gratis, di profil kami ada TO gratis yang bisa langsung dicoba.",
    "buat yang mau pemanasan, TO gratisnya bisa dicek di profil kami.",
    "kalau mau ngukur kesiapan, coba TO gratis di profil kami, skornya langsung kelihatan per kompetensi.",
    "btw, TO gratisnya bisa dicek di profil kami kalau mau latihan dulu sebelum hari H.",
]

# Reaksi kalimat 1 per intent. Semuanya aman: reaksi umum + saran belajar
# yang benar secara umum, TANPA menjawab soal spesifik (jawaban bisa salah)
# dan TANPA mengarang fakta/angka.
REACTIONS = {
    "soal": [
        "soal model gini memang sering muncul di TO, latihan rutin dikit-dikit tiap hari biasanya lebih nempel daripada kebut semalam.",
        "ngerjain soal kayak gini paling enak sambil coret-coret, jadi alurnya kebayang sebelum lihat opsi jawabannya.",
    ],
    "galau": [
        "wajar banget ngerasa gitu, hampir semua pejuang CPNS pernah di fase itu, yang penting jangan berhenti latihan.",
        "capek itu tandanya udah berjuang, istirahat sebentar boleh, tapi jangan sampai berhenti.",
    ],
    "info": [
        "formasi tahun ini memang rame dibahas, semoga dapet formasi yang cocok ya.",
        "info jadwal gini memang bikin deg-degan, sambil nunggu bisa cicil latihan soalnya dulu.",
    ],
    "tips": [
        "tipsnya masuk akal, konsistensi memang kunci, apalagi buat TKP yang butuh jam terbang.",
        "belajar dikit tapi rutin itu jauh lebih nempel daripada sekali duduk berjam-jam.",
    ],
    "skor": [
        "skor segitu udah lumayan buat patokan, tinggal kejar bagian yang masih di bawah ambang.",
        "yang penting skor per kompetensinya kelihatan, jadi tahu persis bagian mana yang perlu dikejar.",
    ],
    "umum": [
        "semangat terus latihannya, konsistensi kecil tiap hari itu yang paling ngaruh.",
        "perjuangan CPNS memang maraton, bukan sprint, pelan-pelan tapi jalan terus.",
    ],
}

_INTENT_PATTERNS = [
    ("soal", re.compile(r"\bsoal\b|jawab|berapa|hitung|pilihan|opsi", re.I)),
    ("galau", re.compile(r"bingung|takut|gagal|capek|lelah|nyerah|menyerah|stres|stress|galau|down|putus asa|pesimis|insecure", re.I)),
    ("info", re.compile(r"formasi|pengumuman|jadwal|pendaftaran|daftar|rekrutmen|penerimaan|kuota", re.I)),
    ("tips", re.compile(r"\btips\b|cara|strategi|belajar|trik|metode", re.I)),
    ("skor", re.compile(r"\bskor\b|nilai|ambang|passing grade|peringkat", re.I)),
]


def detect_intent(text: str) -> str:
    """Intent pertama yang cocok (urutan penting: soal > galau > info > tips > skor)."""
    t = text or ""
    for intent, rx in _INTENT_PATTERNS:
        if rx.search(t):
            return intent
    return "umum"


def softsell_for(index: int) -> str:
    return SOFTSELL[index % len(SOFTSELL)]


def draft_for(text: str, index: int) -> tuple:
    """Buat draf balasan dari isi post. Kembalikan (comment, intent)."""
    intent = detect_intent(text)
    variants = REACTIONS[intent]
    reaction = variants[index % len(variants)]
    comment = reaction + "\n\n" + softsell_for(index)
    return comment, intent


# Pola pelanggaran keras di seluruh balasan.
_HARD_PATTERNS = [
    (re.compile(r"—"), "em-dash (dilarang)"),
    (re.compile(r"their profile", re.I), "'their profile' (pihak ketiga)"),
    (re.compile(r"profil mereka", re.I), "'profil mereka' (pihak ketiga)"),
    (re.compile(r"\b(mereka|their)\b", re.I), "kata ganti orang ketiga 'mereka/their'"),
    (re.compile(r"@[\w.]{2,}", re.I), "'@handle' di dalam balasan (dilarang sebut nama/@handle pemilik post)"),
    (re.compile(r"#\w+"), "hashtag (dilarang)"),
    (re.compile(r"\bLanjutASN (helped|made|bantu aku|bikin aku)\b", re.I), "testimoni palsu tentang LanjutASN"),
    (re.compile(r"\baku lolos\b.*\bLanjutASN\b", re.I), "testimoni palsu 'aku lolos berkat LanjutASN'"),
    (re.compile(r"\bLanjutASN (bisa|membantu|membantumu)\b", re.I), "nama 'LanjutASN' sebagai subjek orang ketiga di kalimat promo"),
    (re.compile(r"Rp\s?[\d.,]+", re.I), "harga dalam balasan (dilarang sebut harga)"),
    (re.compile(r"https?://\S+|www\.\S+", re.I), "tautan di dalam balasan (dilarang)"),
]


def check_identity(text: str) -> list:
    """Kembalikan daftar pelanggaran identitas/gaya dalam satu balasan."""
    problems = []
    for rx, label in _HARD_PATTERNS:
        if rx.search(text or ""):
            problems.append(label)
    # Softsell wajib ada: menunjuk ke profil + menyebut TO gratis.
    if "profil kami" not in (text or ""):
        problems.append("softsell tidak mengarah ke 'profil kami'")
    if "gratis" not in (text or "").lower():
        problems.append("softsell tidak menyebut TO gratis")
    if len(text or "") > 400:
        problems.append(f"terlalu panjang ({len(text)} karakter, maks 400)")
    return problems
