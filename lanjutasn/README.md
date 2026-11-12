# Bot reply @lanjutasn_id — LanjutASN

Bot balasan Threads untuk akun marketing LanjutASN. Replika penuh bot
@blooplyy_ (`/home/ubuntu/threads-bot`, pola Clove/Panah dulu: dir + queue +
keyword sendiri, BUKAN menempel ke bot Blooply). Dibuat 2026-11-13 atas
perintah Amad: keyword hanya ASN/CPNS/PNS/P3K/dsb, target hanya Bahasa
Indonesia, softsell "kalau mau TO gratis bisa cek profil".

## Aturan main

- KEYWORD: hanya post yang berhubungan dengan ASN / CPNS / PNS / P3K / PPPK
  dan turunannya (SKD, SKB, TWK, TIU, TKP, tryout, formasi, seleksi, ambang,
  soal, dsb). Validasi kata kunci kuat ada di `find_posts.py` + `build_pool.py`.
- TARGET: hanya Bahasa Indonesia. Post bahasa lain dibuang di pool.
- SOFTSELL: balasan membantu dulu (kalimat 1 = reaksi isi post), lalu ajakan
  lembut "kalau mau TO gratis bisa cek profil" (6 variasi rotasi di
  `lanjutasn_identity.py`). Tanpa hashtag, tanpa harga, tanpa link.
- GAYA: orang pertama sebagai LanjutASN ("kami"); hangat, natural; tanpa
  em-dash; TANPA menyebut nama/@handle pemilik post (aturan yang sama seperti
  Blooply, 12 Nov 2026).
- SAFETY: anti double-reply (`replied_urls.json` + deep-scan idempotency),
  filter author 24 jam (`posted_history.jsonl`), jangan balas post sendiri,
  jeda 110-135 detik antar balasan, maks 3 gagal beruntun lalu cooldown 12
  menit, retry maks 2x per URL. TEXT-ONLY (tanpa foto).

## File

| File | Fungsi |
|---|---|
| `lanjutasn_identity.py` | Aturan identitas + softsell rotasi + validator draf |
| `keywords.json` | 5 grup keyword pencarian (rotasi per siklus) |
| `find_posts.py` | Scraper pencarian Threads (ID + keyword ASN, max 24 jam) |
| `scraper_cycle.py` | Siklus scrape per grup keyword (rotasi, lock, log) |
| `build_pool.py` | Pool dari arsip found_posts (ID-only, dedupe) |
| `pick_drafts.py` | Pilih 12 kandidat (filter author 24 jam + skip patterns) |
| `draft_comments.py` | Drafter template (reaksi per intent + softsell rotasi) |
| `merge_comments.py` | Gabung comments_new.json ke comments.json |
| `queue_status.py` | Status antrean live |
| `auto_comment.py` | Poster (satu run, maks 4 balasan) — TEXT-ONLY |
| `poster_daemon.py` | Daemon kontinu (dipakai unit systemd) |
| `check_dry_run.py` | Dry-run end-to-end TANPA posting |
| `session.json` | Sesi bot (unlimited; started 2026-11-13) |

Sesi login ada di direktori induk (`../state.json`, `../account.json`,
`../account_guard.py`) — dipakai bersama skrip posting carousel. JANGAN
menyalin state.json dari akun lain.

Interpreter Python: `/home/ubuntu/threads-bot/venv/bin/python` (venv Blooply,
dipakai read-only; sudah terbukti jalan untuk `verify_account.py`).

## Alur (pola Blooply)

```
scraper (30 mnt) -> found_posts_auto_*.json
  -> build_pool.py -> pool_ready.json
  -> pick_drafts.py -> candidates.json (12)
  -> draft_comments.py (template, cadangan) / refill LLM Hermes
     lanjut asn-auto-cycle (utama, LIVE 13 Nov 06:13 — model
     agnes/agnes-2.5-flash via 9router; terbukti: draf LLM menanggapi isi
     post, bukan generik)
     -> comments_new.json -> merge_comments.py -> comments.json
  -> poster_daemon.py (kontinu, jeda 110-135 dtk) -> balasan live
```

## Perintah

```bash
D=threads-lanjut; D=${D}asn; cd "/home/ubuntu/$D/bot"
PY=/home/ubuntu/threads-bot/venv/bin/python

# Dry-run (tanpa posting, tanpa merge):
$PY check_dry_run.py

# Status antrean:
$PY queue_status.py

# Satu run poster manual (maks 4 balasan; HANYA setelah persetujuan):
$PY auto_comment.py

# Jalankan daemon (HANYA setelah persetujuan dry-run):
systemd-run --user --unit=lanjutasn-poster --collect \
  --working-directory="/home/ubuntu/$D/bot" \
  $PY "/home/ubuntu/$D/bot/poster_daemon.py"

# Berhenti:
touch STOPPED   # daemon berhenti di siklus berikutnya
# atau: systemctl --user stop lanjutasn-poster
```

## Yang belum / butuh keputusan Amad

1. **Refill LLM**: LIVE 13 Nov 06:13 (job Hermes `lanjutasn-scraper`
   tiap 30 mnt + `lanjutasn-auto-cycle` tiap 15 mnt, model
   agnes/agnes-2.5-flash via 9router). Drafter template tetap ada sebagai
   cadangan; jalur utama sekarang LLM (terbukti kontekstual: draf ke
   pengumuman formasi menanggapi isi post, bukan generik).
2. **Batas reply per hari/jam**: daemon ikut pola Blooply (16-19/jam, tanpa
   cap harian). Amad bisa menetapkan batas lain.
3. **Persetujuan draf dulu atau langsung posting**: saat ini daemon langsung
   posting dari antrean. Bila Amad mau review draf dulu, alurnya: drafter
   menulis comments_new.json, Amad approve, baru merge + daemon.
4. **Sesi**: bila sesi mati, daemon fail-closed (berhenti, tidak posting).
   Login ulang memakai kredensial di `../.env` — hanya atas arahan Amad.
