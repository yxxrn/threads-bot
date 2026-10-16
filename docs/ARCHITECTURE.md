# Arsitektur

Dua sistem terpisah yang tidak saling bergantung. Bisa dipakai salah satu,
bisa dua-duanya di mesin yang sama.

---

## 1. Autopost — posting ke akun sendiri

Pola: **one-shot**. Tidak ada daemon, tidak ada antrean. Setiap script
dipanggil → post → selesai. Penjadwalan diserahkan ke luar (cron/timer).

```
┌──────────────┐   panggil   ┌─────────────────────────────┐
│ cron/timer/  │────────────▶│  promo_auto.py              │
│ manual       │             │  x_promo_auto.py            │
└──────────────┘             │  x_muse_auto.py             │
                             │  p2_muse_auto.py            │
                             │  post.py / x_post.py / ...  │
                             └──────────┬──────────────────┘
                                        │ Playwright (CloakBrowser)
                                        ▼
                             ┌─────────────────────────────┐
                             │ Threads / X / Facebook web  │
                             └─────────────────────────────┘
```

**Script utama:**

| Script | Target | Fungsi |
|---|---|---|
| `post.py` | Threads | Post teks single/chain (`1/N` badge asli), media per bagian |
| `promo_auto.py` | Threads | Promo Blooply: chain 2 bagian, hook round-robin |
| `p2_muse_auto.py` | Threads | Muse.ai referral: chain 2, ID/EN selang-seling, gating 90-120 menit |
| `p3_post.py` | Threads | Post single generik dari file (warm-up akun kedua) |
| `x_post.py` | X | 1 tweet + media, weighted ≤280 |
| `x_promo_auto.py` | X | Promo Blooply X, hook round-robin |
| `x_muse_auto.py` | X | Muse referral X, gating 90-120 menit |
| `fb_post.py` | FB grup | Post ke 1 grup + verify via search |
| `fb_promo_auto.py` | FB grup | Rotasi grup dari `fb_groups_target.txt` |
| `import_cookies.py` | — | Konversi Netscape cookies → `storage_state*.json` |
| `threads_delete.py` | Threads | Hapus 1 post (menu More → Delete) |
| `verify_seg.py` | Threads | Verifikasi media per segmen chain |

**State:** file `.promo_state.json`, `.x_muse_state.json`, `.p2_muse_state.json`
(masing-masing berisi counter hook + timestamp terakhir). Aman dihapus untuk
reset; tidak berisi kredensial.

---

## 2. Reply bot — balas postingan orang

Pola: **kontinu**. Daemon posting dari antrean; pipeline terpisah mengisi
antrean. Antara keduanya tidak saling memanggil — hanya berbagi file JSON.

```
                 ┌───────────────────── pipeline refill (per 15-30 menit) ────────────────┐
                 │                                                                       │
  scrape ──────▶ found_posts_auto_*.json ──▶ build_pool.py ──▶ pool_ready.json            │
  (find_posts.py / scraper_cycle.py)              │                                        │
                                                  ▼                                        │
                                            pick_drafts.py ──▶ candidates.json            │
                                                  │                                        │
                                                  ▼                                        │
                                 ┌─── penulis komentar (agent LLM ATAU script) ───┐      │
                                 │   baca candidates.json, tulis comments_new.json│      │
                                 └──────────────────────┬─────────────────────────┘      │
                                                        ▼                                 │
                                              merge_comments.py ──▶ comments.json ────────┘
                                                                        │
                 ┌─────────────────────── daemon poster (selalu jalan) ──┘
                 │
                 ▼
   poster_daemon.py ──▶ auto_comment.py ──▶ post reply ke Threads
        │                    (browser: CloakBrowser)
        ├─ baca: comments.json + retry_queue.json
        ├─ tulis: replied_urls.json, posted_history.jsonl, auto_log.json, daemon.log
        └─ lock: .auto_comment.lock (anti double-post)
```

### Komponen

| File | Peran |
|---|---|
| `poster_daemon.py` | Loop utama: ambil antrean → post satu → jeda 45-75s → ulang. Stop otomatis saat `session.json` habis. Restart browser otomatis kalau error beruntun. |
| `auto_comment.py` | Mesin posting: buka URL post → expand composer → ketik komentar → Post → verifikasi. Juga menyimpan state (`replied_urls.json`, `retry_queue.json`). |
| `find_posts.py` | Scrape pencarian Threads per keyword (max umur + limit), output JSON. |
| `scraper_cycle.py` | Rotasi grup keyword dari `scraper_keywords.json`, panggil `find_posts.py` N grup per siklus (default 2; produksi pakai 4 sejak 2026-10-16), tulis `found_posts_auto_<ts>_<a/b>.json`. Ada file lock anti-overlap. `--max-age-hours` default 96; produksi 168 (7 hari). |
| `build_pool.py` | Gabung semua `found_posts*.json` → filter (bahasa, sudah dibalas, dedupe) → `pool_ready.json`. |
| `pick_drafts.py` | Pilih 12 kandidat prioritas ID dari pool → `candidates.json`. Skip author yang baru dibalas (<24 jam) + `skip_urls.txt`. |
| `merge_comments.py` | Gabung `comments_new.json` (hasil tulis komentar) → `comments.json` (antrean daemon). |
| `queue_status.py` | Cetak status antrean 1 baris (live/tombstone/session). Dipakai keputusan refill. |
| `check_refill_state.py` | Diagnostik manual: session + daftar antrean pending |
| `threads_monitor_all.py` | Monitor deterministik: cetak alarm hanya kalau ada masalah (daemon mati, queue macet, cron stuck, dsb). Output stabil = tidak ada alarm. |
| `login.py` / `check_login.py` | Login sekali (simpan `state.json`) + cek validitas sesi. |

### Siapa yang menulis komentar?

Ini **satu-satunya bagian yang butuh "otak"** (LLM). Dua pilihan:

**A. Pakai agent (yang dipakai di produksi saat ini).**
Agent (mis. Hermes) dijadwalkan tiap 15 menit dengan prompt:
jalankan `queue_status.py` → kalau antrean kurang, jalankan
`build_pool.py && pick_drafts.py` → baca `candidates.json` → tulis
`comments_new.json` (satu komentar per kandidat, bahasa mengikuti post) →
`merge_comments.py`. Agent memakai model LLM via API key apa pun.

**B. Tanpa agent (script murni).**
Tulis `refill_cycle.py` sendiri: panggil API LLM (endpoint OpenAI-compatible
apa saja) dengan prompt yang sama, tulis `comments_new.json`, merge. Tidak ada
kode ini di repo karena setiap orang punya preferensi provider berbeda —
tapi semua bahan sudah ada: struktur prompt di
[`docs/SCHEDULING.md`](SCHEDULING.md), contoh I/O di `candidates.json`.

### File state (semua di-gitignore)

| File | Isi | Hilang = ? |
|---|---|---|
| `state.json` | Cookies browser (login) | Harus login ulang |
| `session.json` | Jendela jalan bot (`started_at`, `duration_hours`) | Bot tidak jalan (dianggap tidak ada sesi) |
| `comments.json` | Antrean reply | Antrean kosong (refill isi ulang) |
| `retry_queue.json` | Gagal/retry + tombstone | Item gagal bisa dicoba ulang |
| `replied_urls.json` | URL yang sudah dibalas | Risiko double-reply (hati-hati!) |
| `posted_history.jsonl` | Log sukses + timestamp | Filter author 24 jam hilang |
| `auto_log.json` | 50 hasil terakhir | — (log saja) |
| `pool_ready.json` | Hasil build_pool | Dibangun ulang |
| `candidates.json` | Batch siap draft | Dibangun ulang |
| `skip_urls.txt` | Daftar URL dilarang dipromo (manual) | Bisa salah reply konten sensitif |
| `used_promos.txt` | Riwayat variasi promo (anti-duplikat) | Promo bisa berulang |
| `shots/` | Screenshot debug/verifikasi | — (debug saja) |

---

## Siklus hidup bot

1. **Mulai sesi** — buat `session.json` (`started_at`, `duration_hours: 24`
   atau `null` = tanpa batas). Daemon mulai posting.
2. **Jalan** — daemon posting terus; pipeline refill menjaga antrean.
3. **Watchdog** — cek tiap 30 menit; lapor kalau ada masalah; restart daemon
   kalau mati.
4. **Sesi habis** — daemon berhenti sendiri; watchdog lapor "sesi selesai".
5. **Sesi baru** — perbarui `session.json` (atau bilang "mulai" ke agent kalau
   pakai pola agent).
