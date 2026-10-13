# Threads Unofficial API — Tanpa Browser (Eksperimen)

**Status: TERVERIFIKASI LIVE** (2026-10-13, akun kedua @clovebliz)

Eksperimen ini membuktikan posting/reply/delete/chain ke Threads **tanpa
Chromium sama sekali** — hanya HTTP client (`curl_cffi` dengan TLS
impersonate Chrome) + cookies dari session yang sudah ada.

## Hasil tes

| Aksi | Metode | Status |
|------|--------|--------|
| Baca feed | GraphQL `BarcelonaFeedDirectQuery` | ✅ 4 post asli |
| Post teks | `POST /api/v1/media/configure_text_only_post/` | ✅ live |
| **Upload gambar** | `POST /rupload_igphoto/fb_uploader_<ts>` (raw bytes) | ✅ CDN, pixel-verified |
| **Post media** | `POST /api/v1/media/configure_text_post_app_feed/` | ✅ live + gambar render |
| Reply | endpoint sama + `reply_id` + `barcelona_source_reply_id` | ✅ nempel ke parent |
| Chain (badge n/N) | part 1 post + part 2..n self-reply berantai | ✅ badge 1/3..3/3 |
| Delete | GraphQL `useBarcelonaDeletePostWWWMutation` | ✅ `did_delete: true` |

## Perbandingan resource: API vs browser (diukur 2026-10-13)

Diukur dengan polling `/proc` setiap 0.25 dtk (peak = jumlah RSS seluruh
process tree) di VPS 2 vCPU. Semua test di akun kedua @clovebliz.

| Metrik | Browser (`post.py`) | API (`api_client.py`) | Selisih |
|---|---|---|---|
| **RAM peak — post 1 teks** | 1.452 MB | **37 MB** | ~39x lebih ringan |
| **RAM peak — chain 3 part** | 1.469 MB | **37 MB** | ~40x lebih ringan |
| **RAM peak — post 1 gambar** | 1.438 MB | **37 MB** | ~39x lebih ringan |
| **Proses** | 11 (Chromium + zygote + renderer) | **1** (Python) | 11x lebih sedikit |
| **Waktu — post 1 teks** | 27,7 dtk | **4,1 dtk** | ~7x lebih cepat |
| **Waktu — chain 3 part** | 55,6 dtk | **20,5 dtk** | ~2,7x lebih cepat |
| **Waktu — post 1 gambar** | 30,4 dtk | **11,2 dtk** | ~2,7x lebih cepat |
| **CPU — post 1 teks** | 6,0 dtk | **0,2 dtk** | ~30x lebih ringan |
| **CPU — chain 3 part** | 7,9 dtk | **0,2 dtk** | ~40x lebih ringan |
| **CPU — post 1 gambar** | 6,2 dtk | **0,2 dtk** | ~31x lebih ringan |
| **Trafik — post 1 teks** | RX 12.125 KB / TX 857 KB | **RX 153 KB / TX 33 KB** | ~79x lebih hemat |
| **Disk** | 658 MB (`.pw-browsers`) | **38 MB** (curl_cffi) | ~17x lebih kecil |

**Kasus daemon (persistent browser) — paling dramatis:** daemon reply-bot
(`poster_daemon.py`) memakai **2.368 MB RAM / 11 proses terus-menerus**
selama hidupnya (Chromium tetap jalan). Versi API hanya butuh **37 MB per
invokasi** — dan karena tidak ada browser yang standby, RAM kembali ke nol
setelah selesai. Di VPS 8 GB, ini perbedaan antara 30% RAM terpakai permanen
vs ~0,5%.

**Kapan pakai yang mana:**
- **API** — volume tinggi (scrape feed, reply massal, chain, post media),
  VPS RAM kecil, atau kuota trafik ketat. Jauh lebih ringan + cepat.
- **Browser** — posting penting jangka panjang (API internal bisa berubah),
  video/carousel (belum diimplementasi di api_client — baru gambar tunggal),
  atau kalau session sering diminta verifikasi ulang oleh Meta.

## Cara kerja

1. **Cookies** dari `storage_state*.json` (sessionid, csrftoken, ds_user_id,
   mid, ig_did). Login tetap butuh browser sekali; setelah itu HTTP murni.
2. **Token anti-CSRF** `fb_dtsg` + `lsd` di-scrape dari HTML homepage via
   GET biasa (regex `"DTSGInitialData",[],{"token":"..."}` dan `"LSD"`).
3. Semua request pakai header:
   - `x-ig-app-id: 238260118697367` (app ID web Threads)
   - `x-csrftoken`, `x-asbd-id: 359341`, `x-web-session-id` (format `a:b:c`)
   - `user-agent` Chrome + `impersonate="chrome"` di curl_cffi (TLS fingerprint)

## Upload media (gambar) — cara kerja

Dua langkah, dua endpoint berbeda:

1. **Upload** — `POST /rupload_igphoto/fb_uploader_<ts>` dengan **raw bytes**
   gambar sebagai body (bukan form-data). Header wajib:
   - `content-type` + `x-entity-type`: `image/jpeg` / `image/png`
   - `x-entity-length`: ukuran bytes, `x-entity-name`: `fb_uploader_<ts>`
   - `x-instagram-rupload-params`: JSON `{is_sidecar, is_threads:1,
     media_type:1, upload_id, upload_media_height, upload_media_width}`
   - `offset: 0`
   Respons: `{"upload_id": "...", "status": "ok"}`.
2. **Configure** — `POST /api/v1/media/configure_text_post_app_feed/`
   (**endpoint berbeda** dari post teks!). Form-nya sama seperti post teks,
   tapi: `is_threads=true`, `upload_id=<hasil upload>`, `usertags=`,
   ada `gif_media_id: null` di tpi, dan **tanpa** `publish_mode`.

Dimensi gambar dibaca dari bytes langsung (parser JPEG/PNG tanpa dependensi)
untuk mengisi `upload_media_width/height`.

**Terverifikasi:** pixel gambar di CDN = warna asli file (sample tengah
RGB 30,99,200 persis). JPEG dan PNG dua-duanya jalan.

## Temuan penting

- **Reply butuh DUA parameter**: `barcelona_source_reply_id` (form field)
  **DAN** `text_post_app_info.reply_id` (JSON di dalam tpi). Kalau hanya satu,
  reply jadi **post terpisah**, bukan menempel ke parent.
- **Chain = self-reply berantai**: post part 1, lalu reply ke part 1, lalu
  reply ke part 2, dst. Badge `n/N` muncul otomatis. Jeda ~4 detik antar part.
- **Delete part 1 = seluruh chain terhapus.**
- **Media pakai endpoint configure BERBEDA**: teks →
  `configure_text_only_post/`, media → `configure_text_post_app_feed/`.
- **Feed** butuh ~39 variable relay-provider lengkap (disimpan di
  `feed_vars.json`); versi minimal 3 variable balik error
  `missing_required_variable_value`.
- Respons post berisi `integrity_review_decision: "pending"` (moderasi Meta) —
  post tetap live normal.

## Risiko & batasan

- Ini **API internal Meta** (dipakai web app mereka). `doc_id` GraphQL dan
  struktur parameter bisa berubah sewaktu-waktu tanpa pemberitahuan.
- Kalau endpoint berubah → capture ulang call asli dari browser
  (`capture2.py` / `capture_chain.py`), update `doc_id`/parameter.
- Untuk tugas volume tinggi (scrape feed, reply massal) API ini jauh lebih
  ringan dari browser. Untuk posting penting, browser (Playwright) lebih tahan
  perubahan jangka panjang.
- Tidak ada rate-limit yang kelihatan di tes kecil, tapi tetap pasang jeda
  antar request (≥ 4 detik) seperti pola browser.

## File

| File | Fungsi |
|------|--------|
| `api_client.py` | Client lengkap: feed, post, reply, chain, media, delete (multi-akun via `--state`) |
| `feed_vars.json` | 39 variable GraphQL feed (hasil capture) |
| `capture.py` | Rekam call `/api/` saat browse (tanpa post) |
| `capture2.py` | Rekam call saat post 1 teks (reuse alur `post.py`) |
| `capture_chain.py` | Rekam call saat chain 2 part |
| `capture_media.py` | Rekam call upload + configure saat post gambar |
| `capture_delete.py` | Rekam call saat delete via UI |
| `captures/` | Hasil capture referensi (publish + delete + media) |

## Pemakaian

```bash
cd ~/threads-playwright
.venv/bin/python api_client.py feed                          # baca feed
.venv/bin/python api_client.py post "teks"                   # post teks
.venv/bin/python api_client.py media foto.jpg "caption"      # post gambar
.venv/bin/python api_client.py reply <pk> "teks"             # reply ke post
.venv/bin/python api_client.py chain "p1" "p2" "p3"          # chain n/N
.venv/bin/python api_client.py delete <pk>                   # hapus post sendiri
# akun lain: tambah --state storage_state_p3.json
```

## Cara capture ulang (kalau endpoint berubah)

```bash
# 1. post test via browser sambil rekam
.venv/bin/python capture2.py --headless --post "test"
# 2. lihat call publish di captures/capture2_*.json
# 3. update api_client.py sesuai field yang berubah
# 4. hapus test post: api_client.py delete <pk>
```

**Catatan:** `capture*.py` membutuhkan login session di `storage_state.json`.
Test post yang dibuat saat capture harus dihapus setelah selesai.
