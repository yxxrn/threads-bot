# reply-bot — bot balas postingan orang

Bot yang membalas postingan orang lain di Threads dengan komentar natural
(kalimat 1) + promosi halus di kalimat kedua. Semua via browser otomasi.

## Arsitektur singkat

```
scrape ──▶ found_posts_auto_*.json ──▶ build_pool.py ──▶ pool_ready.json
                                            │
                                      pick_drafts.py ──▶ candidates.json
                                            │
                            ┌── penulis komentar (LLM) ──┐
                            │   → comments_new.json      │
                            └──────────┬─────────────────┘
                                       ▼
                              merge_comments.py ──▶ comments.json
                                                        │
                                    poster_daemon.py ◀──┘
                                    (posting terus, jeda 110-135s)
```

Detail lengkap: [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md).

## Mengatur kecepatan posting (rate)

Rate ditentukan `GAP_MIN, GAP_MAX` di `auto_comment.py` (baris ~36). Jeda
adalah waktu tunggu **antar** post; durasi posting sendiri ~85-100 detik.

```
rate (post/jam) ≈ 3600 / (gap_rata-rata + durasi_post)
```

| Target rate | GAP_MIN, GAP_MAX | Catatan |
|---|---|---|
| ~26/jam (lama) | 45, 75 | agresif — dipakai sampai 2026-10-13 |
| **~16-19/jam (sekarang)** | **110, 135** | target 15-20/jam |
| ~12-13/jam | 170, 210 | kalau perlu lebih santai |

Setelah ubah `GAP_MIN/GAP_MAX`, **restart daemon** supaya nilai baru dipakai:
`systemctl --user restart threads-poster-daemon-3.service` (unit transient
dibuat oleh sistem penjadwal; kalau tidak ada, jalankan ulang
`poster_daemon.py` sebagai background process).

## File inti

| File | Fungsi |
|---|---|
| `poster_daemon.py` | Daemon posting kontinu dari antrean; stop saat sesi habis |
| `auto_comment.py` | Mesin posting (buka post → ketik → Post → verifikasi) |
| `find_posts.py` | Scrape pencarian Threads per keyword |
| `scraper_cycle.py` | Rotasi keyword → jalankan find_posts → `found_posts_auto_*.json` |
| `build_pool.py` | Gabung + filter arsip scrape → `pool_ready.json` |
| `pick_drafts.py` | Pilih 12 kandidat prioritas ID → `candidates.json` |
| `merge_comments.py` | `comments_new.json` → `comments.json` (antrean) |
| `queue_status.py` | Status antrean 1 baris (untuk keputusan refill) |
| `check_refill_state.py` | Diagnostik: sesi + antrean pending |
| `threads_monitor_all.py` | Watchdog: alarm hanya saat ada masalah (output deterministik) |
| `login.py` / `check_login.py` | Login & cek sesi (`state.json`) |
| `scraper_keywords.json` | Grup keyword rotasi scraper |
| `WATCHDOG.md` | Playbook yang dijalankan agent saat alarm |
| `tools/fetch_refill.py` | Helper: fetch teks penuh beberapa URL (manual) |
| `promo.jpg` | Gambar promo yang dilampirkan ke balasan |

## Setup

```bash
python3 -m venv venv
./venv/bin/pip install cloakbrowser==0.5.11 playwright==1.63.0

# Login (interaktif) ATAU import cookies:
./venv/bin/python login.py
./venv/bin/python check_login.py   # harus "OK"
```

Buat `session.json` (jendela bot):

```bash
./venv/bin/python - <<'PY'
import json, datetime
json.dump({"started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "duration_hours": 24}, open("session.json", "w"), indent=1)
PY
```

`duration_hours`: `null` = tanpa batas.

## Jalankan

```bash
# Daemon (systemd direkomendasikan):
systemd-run --user --unit=threads-poster-daemon --collect \
  --working-directory=$PWD $PWD/venv/bin/python $PWD/poster_daemon.py

# Isi antrean pertama:
./venv/bin/python scraper_cycle.py
./venv/bin/python build_pool.py && ./venv/bin/python pick_drafts.py
# → tulis comments_new.json (lihat catatan di bawah)
./venv/bin/python merge_comments.py
```

### Penulis komentar (`comments_new.json`)

Antara `pick_drafts.py` dan `merge_comments.py` ada satu langkah yang butuh
LLM: menulis komentar untuk tiap kandidat di `candidates.json`, hasilnya
ditulis ke `comments_new.json`:

```json
[
  {"url": "...", "author": "...", "lang": "id",
   "comment": "kalimat 1 reaksi natural...\n\nkalimat 2 promo halus"}
]
```

Bisa dilakukan oleh **agent apa pun** (prompt lengkap di
[`../docs/SCHEDULING.md`](../docs/SCHEDULING.md)) atau **script sendiri**
yang memanggil API LLM (contoh di
[`../docs/PORTING.md`](../docs/PORTING.md)).

### Aturan komentar (WAJIB)

- Bahasa mengikuti bahasa post (`id` → Indonesia casual, `en` → English casual).
- **Kalimat 1**: murni reaksi isi post — tidak boleh sebut produk.
- Baris kosong, lalu **kalimat 2**: promosi halus (AI pemotong video panjang
  jadi shorts; arahkan ke profil; tanpa link; no hard selling).
- Natural manusia, tanpa em-dash, variasikan (cek `used_promos.txt`).
- Konten sensitif (duka, politik, jasa/solicitation) → masuk `skip_urls.txt`,
  jangan dibalas.

## File state penting

| File | Isi | Jangan dihapus? |
|---|---|---|
| `state.json` | Cookies login | — (login ulang kalau hilang) |
| `session.json` | Jendela bot | — (buat baru) |
| `comments.json` | Antrean | Boleh (refill isi ulang) |
| `retry_queue.json` | Retry + tombstone | ⚠️ tombstone cegah re-queue |
| `replied_urls.json` | Sudah dibalas | ⚠️⚠️ tanpa ini bisa double-reply |
| `posted_history.jsonl` | Riwayat sukses | ⚠️ dipakai filter author 24 jam |
| `skip_urls.txt` | URL dilarang dipromo | ⚠️ (manual, jaga) |
| `used_promos.txt` | Riwayat variasi promo | ⚠️ (anti-duplikat) |

## Watchdog

`threads_monitor_all.py` mencetak alarm **hanya** saat ada yang perlu
ditindak (output kosong = sehat; output deterministik, tanpa timestamp —
dipakai sebagai monitor gate di penjadwal). Alarm yang mungkin muncul:

- `daemon poster TIDAK jalan` → restart via systemd-run (lihat WATCHDOG.md)
- `antrian kosong >3 jam` → cek scraper/refill
- `cron worker STUCK >45 menit` → kill + trigger ulang
- `>=3 akun gagal di-reply dalam 2 jam` → diagnosa error
- `sesi sudah habis` → lapor, jangan posting

Tindak lanjut lengkap: [`WATCHDOG.md`](WATCHDOG.md).
