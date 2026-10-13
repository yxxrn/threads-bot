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
| Reply | endpoint sama + `reply_id` + `barcelona_source_reply_id` | ✅ nempel ke parent |
| Chain (badge n/N) | part 1 post + part 2..n self-reply berantai | ✅ badge 1/3..3/3 |
| Delete | GraphQL `useBarcelonaDeletePostWWWMutation` | ✅ `did_delete: true` |

## Cara kerja

1. **Cookies** dari `storage_state*.json` (sessionid, csrftoken, ds_user_id,
   mid, ig_did). Login tetap butuh browser sekali; setelah itu HTTP murni.
2. **Token anti-CSRF** `fb_dtsg` + `lsd` di-scrape dari HTML homepage via
   GET biasa (regex `"DTSGInitialData",[],{"token":"..."}` dan `"LSD"`).
3. Semua request pakai header:
   - `x-ig-app-id: 238260118697367` (app ID web Threads)
   - `x-csrftoken`, `x-asbd-id: 359341`, `x-web-session-id` (format `a:b:c`)
   - `user-agent` Chrome + `impersonate="chrome"` di curl_cffi (TLS fingerprint)

## Temuan penting

- **Reply butuh DUA parameter**: `barcelona_source_reply_id` (form field)
  **DAN** `text_post_app_info.reply_id` (JSON di dalam tpi). Kalau hanya satu,
  reply jadi **post terpisah**, bukan menempel ke parent.
- **Chain = self-reply berantai**: post part 1, lalu reply ke part 1, lalu
  reply ke part 2, dst. Badge `n/N` muncul otomatis. Jeda ~4 detik antar part.
- **Delete part 1 = seluruh chain terhapus.**
- **Feed** butuh ~39 variable relay-provider lengkap (disimpan di
  `feed_vars.json`); versi minimal 3 variable balik error
  `missing_required_variable_value`.
- **Endpoint publish adalah REST** (bukan GraphQL):
  `/api/v1/media/configure_text_only_post/`
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
| `api_client.py` | Client lengkap: feed, post, reply, chain, delete (multi-akun via `--state`) |
| `feed_vars.json` | 39 variable GraphQL feed (hasil capture) |
| `capture.py` | Rekam call `/api/` saat browse (tanpa post) |
| `capture2.py` | Rekam call saat post 1 teks (reuse alur `post.py`) |
| `capture_chain.py` | Rekam call saat chain 2 part |
| `capture_delete.py` | Rekam call saat delete via UI |
| `captures/` | Hasil capture referensi (publish + delete) |

## Pemakaian

```bash
cd ~/threads-playwright
.venv/bin/python api_client.py feed                       # baca feed
.venv/bin/python api_client.py post "teks"                # post
.venv/bin/python api_client.py reply <pk> "teks"          # reply ke post
.venv/bin/python api_client.py chain "p1" "p2" "p3"       # chain n/N
.venv/bin/python api_client.py delete <pk>                # hapus post sendiri
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
