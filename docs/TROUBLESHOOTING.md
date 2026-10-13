# Troubleshooting

Masalah yang sudah pernah kejadian di produksi + solusinya. Baca ini dulu
sebelum debug dari nol.

---

## Session / login

### `ERR_TOO_MANY_REDIRECTS` + `sessionid=deleted`

**Gejala:** semua script gagal navigasi; curl ke Threads balikin
`set-cookie: sessionid=deleted` dan redirect loop.

**Penyebab:** Meta me-reset session server-side (logout paksa). Sering
terjadi kalau cookie di-export dari device yang sama berulang-ulang, atau
akun "kelihatan" bot.

**Solusi:** import cookies fresh dari browser:

```bash
python import_cookies.py cookies_baru.txt storage_state.json .threads.com
# cek:
curl -s -b "sessionid=..." -o /dev/null -w "%{http_code}" https://www.threads.com/
```

Kalau masih `deleted` setelah cookies fresh → tunggu beberapa jam, jangan
spam login. Akun bisa butuh "istirahat".

### `login page` muncul padahal cookies baru

- Cek domain cookies: harus `.threads.com` (atau `.instagram.com` untuk
  beberapa cookie).
- `import_cookies.py` butuh format Netscape (tab-separated), bukan JSON
  extension mentah.
- Cookie `sessionid` harus milik akun yang benar — verifikasi dengan
  `ds_user_id` yang diharapkan.

### CloakBrowser vs stock

Script otomatis fallback ke stock chromium kalau CloakBrowser gagal. Untuk
memaksa stock: set env `BLOOPLY_BROWSER=stock` (post.py), `X_BROWSER=stock`
(x_post.py), `FB_BROWSER=stock` (fb_post.py).

Kalau error `Executable doesn't exist` → browser belum terinstall:

```bash
.venv/bin/playwright install chromium
# atau untuk reply-bot:
./venv/bin/playwright install chromium
```

---

## Posting

### Chain hanya terkirim sebagian (mis. 3 dari 5 bagian)

**Penyebab:** Meta kadang hanya publish beberapa bagian pertama kalau slot
tidak "disentuh ulang" sebelum klik Post.

**Solusi:** ini sudah ditangani `_commit_all_slots` di `post.py` (re-touch/blur
tiap slot). Kalau masih terjadi, jangan tambah bagian > 10 dalam satu chain,
dan pastikan tidak ada perubahan selector Threads. Cek `last_post.png` untuk
melihat state terakhir.

### Media nyangkut di bagian 1 (chain)

**Penyebab:** memakai `[aria-label="Attach media"]` (itu carousel ROOT).

**Solusi:** sudah diperbaiki — bagian 2+ memakai tombol foto 36px di toolbar
baris itu (climb dari editor baris). Jangan "perbaiki" ke selector lama.

### Verify gagal padahal post sukses

- `post.py` kadang print URL profil (fallback) kalau ekstraksi permalink
  gagal — cek `last_post_profile.png` atau buka profil manual.
- Untuk X: verify harus normalize `https://` karena X auto-linkify domain.
- Untuk FB: verify WAJIB via `/search/?q=` — feed tidak render post baru
  di mode otomasi. Sukses = composer "Create post" tertutup.

### Post tidak muncul di pencarian (FB)

Pending approval admin grup → WARN non-fatal. Bukan bug.

---

## Reply bot

### Daemon `queue empty` terus

Antrean kosong = pipeline refill tidak jalan. Cek berurutan:

```bash
./venv/bin/python queue_status.py        # berapa live?
./venv/bin/python check_refill_state.py  # session + pending
ls -t found_posts_auto_*.json | head -3  # scrape terakhir kapan?
tail -5 scraper.log                      # scraper jalan?
```

Kalau `found_posts_auto_*.json` lama → jalankan `scraper_cycle.py` manual.
Kalau scrape jalan tapi queue tetap kosong → cek penulis komentar (agent/script)
jalan atau tidak; lihat `candidates.json` ada isinya atau tidak.

### Daemon mati berulang

**JANGAN** restart pakai `nohup` dari dalam sesi cron/agent — proses ikut mati
saat sesi selesai. Pakai systemd:

```bash
systemd-run --user --unit=threads-poster-daemon --collect \
  --working-directory=$PWD $PWD/venv/bin/python $PWD/poster_daemon.py
```

Kalau unit bentrok ("already exists") padahal proses tidak ada:

```bash
systemctl --user reset-failed threads-poster-daemon
# atau pakai nama baru: --unit=threads-poster-daemon-2
```

### Double-post (URL sama dibalas 2x)

Cek `replied_urls.json` — URL harus masuk situ setelah sukses. Kalau file ini
hilang/korup, risiko double-reply tinggi. File ini JANGAN dihapus.

Tombstone di `retry_queue.json` (`"dead": true`) mencegah draft yang gagal
kembali masuk antrean — jangan dibersihkan sembarangan.

### Komentar kepanjangan / kependek

Threads membatasi panjang komentar (≈500 char). Agent penulis komentar harus
jaga kalimat 1 + promo ≤ batas. Kalau post gagal karena ini, cek
`auto_log.json` bagian `error`.

### Reply kena "pending approval" terus

Itu fitur author-gate Threads (penulis post membatasi balasan). Status
`skipped: pending_author_approval` di history = **bukan** error; daemon
otomatis tidak retry.

---

## Scraper

### `scraper.log` tidak update

- Cek lock: `.scraper_cycle.lock` — kalau ada proses lain masih jalan,
  cycle baru akan skip (by design).
- Cek `state.json` ada (login valid).
- Timeout per grup 600s; keyword yang terlalu umum bisa lambat.

### Hasil scrape banyak bahasa asing

`build_pool.py` memfilter Vietnam/Korea/CJK/Thai/Arab → `other`. Kalau
kebanyakan ID post malah ke-filter, tambahkan kata khas ke `ID_WORDS`
di `build_pool.py`.

### Konten sensitif dapat balasan promo

Tambahkan URL-nya ke `skip_urls.txt` (satu URL per baris, `#` = komentar).
`pick_drafts.py` otomatis skip. Contoh kasus yang sudah ditangani:
solicitation/jasa, ragebait politik, konten duka, konten dewasa.

---

## Penjadwal (Hermes)

### Job tidak fire

```bash
hermes cron list                    # status semua job
hermes cron resume <job_id>        # kalau paused
```

### Delivery gagal ke Telegram (thread not found)

Thread/topic Telegram bisa hilang (dihapus, atau bot ganti). Gejala di log:
`Thread <id> not found, retrying without message_thread_id`.

**Solusi:** buat topic baru via Bot API, lalu update origin job:

```bash
TOKEN=<bot_token>
curl -sS -X POST "https://api.telegram.org/bot${TOKEN}/createForumTopic" \
  -H 'Content-Type: application/json' \
  -d '{"chat_id":<chat_id>,"name":"Threads Bot"}'
# catat message_thread_id dari respons, lalu update origin di jobs.json
```

### Gateway mati mendadak

Cek RAM (`free -m`) — browser Chromium boros. Kalau OOM, kurangi jumlah
browser paralel atau tambah RAM/swap.

Cek juga cron sistem yang mungkin sengaja restart gateway
(`crontab -l` di user terkait).

---

## Portabilitas umum

### Script jalan di mesin A, gagal di mesin B

Cek berurutan:

1. Versi Python sama? (`python3 --version` — repo pakai 3.11)
2. Venv terpisah per folder? Jangan campur `autopost/.venv` dan
   `reply-bot/venv`.
3. Browser terinstall? (`playwright install chromium`)
4. Path di prompt cron/wrapper masih hardcode mesin lama?
5. File state (state.json, session.json, dsb.) sudah dicopy?
6. Jam/timezone mesin — jadwal cron bisa geser kalau beda TZ.
