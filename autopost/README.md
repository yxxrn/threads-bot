# autopost — posting ke akun sendiri

Script one-shot untuk posting ke Threads / X / Facebook dari akun sendiri.
Tanpa API resmi — semuanya via browser (Playwright + CloakBrowser stealth).

## Isi

| File | Fungsi |
|---|---|
| `post.py` | Post Threads: single **atau chain asli** (badge `1/N`) + media per bagian |
| `promo_auto.py` | Promo Blooply: chain 2 bagian, hook round-robin (state `.promo_state.json`) |
| `p2_muse_auto.py` | Muse.ai referral Threads: chain 2, ID/EN selang-seling, gating 90-120 menit |
| `p3_post.py` | Post single generik dari file teks (akun kedua/warm-up) |
| `x_post.py` | 1 tweet + media, weighted ≤280 (URL dihitung 23) |
| `x_promo_auto.py` | Promo Blooply X: 1 tweet + foto, hook round-robin |
| `x_muse_auto.py` | Muse referral X: gating 90-120 menit, EN/ID selang-seling |
| `fb_post.py` | Post ke 1 grup FB + verifikasi via search |
| `fb_promo_auto.py` | Rotasi grup FB dari `fb_groups_target.txt` |
| `import_cookies.py` | Konversi cookies Netscape → `storage_state*.json` |
| `threads_delete.py` | Hapus 1 post Threads (menu More → Delete) |
| `verify_seg.py` | Verifikasi media per segmen chain |
| `cleanup_tests.py` | Hapus post-post tes (batch, dari daftar URL) |
| `login.py` | Login interaktif (butuh GUI) → `storage_state.json` |

## Pakai dasar

```bash
cd autopost
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# Post single:
.venv/bin/python post.py "halo"

# Chain (badge 1/3..3/3):
.venv/bin/python post.py "1/3" "2/3" "3/3"

# Chain + media per bagian (- = teks saja):
.venv/bin/python post.py --media a.mp4 --media b.jpg --media - "1/3" "2/3" "3/3"

# Dari file (pisah dengan --- atau baris kosong):
.venv/bin/python post.py -f thread.txt

# Akun lain (state + profil berbeda):
.venv/bin/python post.py --state storage_state_p3.json \
  --profile-url "https://www.threads.com/@namaakun" "teks"

# X:
.venv/bin/python x_post.py "tweet text" --media foto.jpg

# Hapus post:
.venv/bin/python threads_delete.py --url https://www.threads.com/@user/post/xxx
```

## Cron (contoh)

```cron
0 */4 * * * cd $HOME/threads-bot/autopost && .venv/bin/python promo_auto.py
0 */4 * * * cd $HOME/threads-bot/autopost && .venv/bin/python x_promo_auto.py
*/30 * * * * cd $HOME/threads-bot/autopost && .venv/bin/python x_muse_auto.py
```

Script `*_auto.py` dengan gating (muse) mencetak **stdout kosong** kalau
belum jatuh tempo — aman dijadwalkan sering.

## Media

Script promo memakai file di `media/`:

| Script | File |
|---|---|
| `promo_auto.py`, `x_promo_auto.py`, `fb_promo_auto.py` | `media/blooply-library.jpg` |
| `p2_muse_auto.py` | `media/p2-muse-1-pawxy.jpg` … `-5-spek-vps.jpg` (3+2 carousel) |
| `x_muse_auto.py` | `media/p2-muse-3-kode.jpg` |

Folder `media/` tidak dibundel di git (gambar milikmu). Buat folder dan taruh
file dengan nama di atas, atau edit path di script.

## Gotcha penting (sudah teruji salah-benar)

- **Chain asli HARUS** via multi-composer "Add to thread" + re-touch/blur tiap
  slot sebelum klik Post — tanpa itu Meta terima ~3 bagian saja.
- Klik Post wajib `exact=True` "Post" (bukan "Post Options").
- **Media bagian 2+**: tombol foto 36px di toolbar baris itu (climb dari
  editor baris). `[aria-label="Attach media"]` = carousel ROOT → media
  nyangkut di 1/3. Jangan pakai selector itu.
- Tunggu preview **di dalam baris** sebelum lanjut.
- Verifikasi post: direct URL suka redirect home → buka via klik dari profil.
- Test post = hapus setelah selesai (menu More → Delete; hanya root chain).
- X: verifikasi harus normalize `https://` (X auto-linkify domain).
- FB: verifikasi WAJIB via `/search/?q=` — feed tidak render post baru.
- Cookies pernah bocor via chat → anggap bocor, rotate kalau paranoid.
- Browser: CloakBrowser dulu; fallback stock chromium kalau gagal
  (env `BLOOPLY_BROWSER=stock` / `X_BROWSER=stock` / `FB_BROWSER=stock`).

## Sesi

Session = `storage_state*.json` (Playwright storage state; chmod 600, jangan
git). Kalau kena logout paksa server (`ERR_TOO_MANY_REDIRECTS` +
`sessionid=deleted`), import cookies fresh:

```bash
.venv/bin/python import_cookies.py cookies_baru.txt storage_state.json .threads.com
```
