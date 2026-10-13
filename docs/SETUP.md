# Setup di mesin baru

Panduan dari nol: VPS Ubuntu headless (atau PC Linux). Windows/Mac juga bisa
dengan penyesuaian kecil (path venv).

## 0. Prasyarat

- Python **3.11+** (repo di produksi pakai 3.11.16)
- Git, `curl`
- Akses internet (untuk download browser pertama kali)
- ~1 GB RAM free per browser yang jalan

```bash
sudo apt update && sudo apt install -y python3 python3-venv git curl
```

---

## A. Setup autopost

```bash
cd autopost
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# requirements: playwright, python-dotenv

# Browser: CloakBrowser diunduh otomatis saat pertama dipakai.
# Alternatif stock chromium (kalau CloakBrowser bermasalah):
.venv/bin/playwright install chromium
```

### Login / session

Pilih salah satu:

**1. Import cookies (paling praktis di server headless).**
Export cookies dari browser (extension Cookie-Editor) → file Netscape
`cookies.txt` → konversi:

```bash
.venv/bin/python import_cookies.py cookies.txt storage_state.json .threads.com
# untuk X:  import_cookies.py x_cookies.txt storage_state_x.json .x.com,.twitter.com
# untuk FB: import_cookies.py fb_cookies.txt storage_state_fb.json .facebook.com
```

**2. Login interaktif** (butuh GUI/DISPLAY):

```bash
.venv/bin/python login.py
```

> **Ganti akun** = ganti file `storage_state*.json`. `post.py` menerima
> `--state storage_state_p3.json --profile-url https://www.threads.com/@nama`.

### Tes

```bash
.venv/bin/python post.py "tes posting"
# hapus lagi: .venv/bin/python threads_delete.py --url <permalink>
```

### Media (opsional)

Letakkan gambar/video di `media/`. Script promo (`promo_auto.py`,
`x_promo_auto.py`, `p2_muse_auto.py`) meng-hardcode nama file berikut —
sesuaikan atau ganti dengan punyamu:

- `media/blooply-library.jpg` — foto promo Blooply
- `media/p2-muse-1-pawxy.jpg` … `p2-muse-5-spek-vps.jpg` — carousel muse
  (3 gambar bagian 1 + 2 gambar bagian 2)

---

## B. Setup reply bot

```bash
cd reply-bot
python3 -m venv venv
./venv/bin/pip install cloakbrowser==0.5.11 playwright==1.63.0
```

### Login / session

```bash
# Login interaktif (butuh DISPLAY) atau import cookies:
./venv/bin/python login.py

# Cek validitas:
./venv/bin/python check_login.py
```

`login.py` menyimpan ke `state.json` (chmod 600 otomatis). Kalau `check_login.py`
bilang invalid → login ulang / import cookies baru.

### Mulai sesi bot

```bash
./venv/bin/python - <<'PY'
import json, datetime
json.dump({
  "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
  "duration_hours": 24
}, open("session.json", "w"), indent=1)
PY
```

`duration_hours`: angka = batas jam; `null` = jalan tanpa batas sampai di-stop.

### Jalankan daemon

```bash
# Cara simpel (mati kalau SSH ditutup):
nohup ./venv/bin/python poster_daemon.py >> daemon.log 2>&1 &

# Cara tahan-mati (systemd user unit — direkomendasikan):
systemd-run --user --unit=threads-poster-daemon --collect \
  --working-directory=$PWD \
  $PWD/venv/bin/python $PWD/poster_daemon.py
```

Verifikasi: `pgrep -f poster_daemon.py` dan `tail -3 daemon.log`
(harus muncul `daemon started` lalu `posting ...`).

### Isi antrean pertama

Antrean kosong = daemon idle. Isi dengan pipeline:

```bash
# 1. Scrape post (keyword bisa diedit di scraper_keywords.json)
./venv/bin/python scraper_cycle.py --groups 2 --limit 20

# 2. Bangun pool + pilih kandidat
./venv/bin/python build_pool.py
./venv/bin/python pick_drafts.py

# 3. Tulis komentar untuk tiap kandidat → comments_new.json
#    (lihat docs/ARCHITECTURE.md bagian "Siapa yang menulis komentar")

# 4. Merge ke antrean
./venv/bin/python merge_comments.py
```

### Penjadwalan

Lihat [`docs/SCHEDULING.md`](SCHEDULING.md) — ada 3 pilihan: crontab murni,
systemd timer, atau Hermes cron (yang dipakai di produksi).

---

## C. Setup penjadwal (opsional, kalau tidak pakai Hermes)

### Crontab murni

```bash
crontab -e
```

Contoh isi (sesuaikan path):

```cron
# Autopost: promo Threads tiap 4 jam
0 */4 * * * cd $HOME/threads-bot/autopost && .venv/bin/python promo_auto.py >> cron.log 2>&1

# Reply bot: scrape tiap 30 menit
*/30 * * * * cd $HOME/threads-bot/reply-bot && ./venv/bin/python scraper_cycle.py >> cron.log 2>&1

# Reply bot: refill tiap 15 menit (butuh penulis komentar — lihat docs)
*/15 * * * * cd $HOME/threads-bot/reply-bot && ./venv/bin/python build_pool.py && ./venv/bin/python pick_drafts.py >> cron.log 2>&1
```

### systemd timer (lebih rapi)

Contoh unit untuk scraper — buat 2 file di `~/.config/systemd/user/`:

`threads-scraper.service`:

```ini
[Unit]
Description=Threads bot scraper cycle

[Service]
Type=oneshot
WorkingDirectory=%h/threads-bot/reply-bot
ExecStart=%h/threads-bot/reply-bot/venv/bin/python scraper_cycle.py
```

`threads-scraper.timer`:

```ini
[Unit]
Description=Threads scraper every 30 min

[Timer]
OnCalendar=*:0/30
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now threads-scraper.timer
```

---

## D. Kalau pakai Hermes (seperti di produksi)

Hermes = agent LLM dengan penjadwal cron bawaan. Dipakai karena bisa
menjalankan **bagian yang butuh LLM** (menulis komentar) sekaligus.

```bash
# Refill (agent — menulis komentar):
hermes cron create "every 15m" --name threads-auto-cycle \
  --deliver telegram:CHAT_ID --prompt "$(cat reply-bot/refill_prompt.txt)"

# Scraper (no-agent — script murni):
hermes cron create "every 30m" --name threads-scraper --no-agent \
  --script threads_scraper.sh

# Watchdog (monitor — agent hanya jalan saat ada perubahan status):
hermes cron create "every 30m" --name threads-watchdog \
  --monitor-script threads_monitor_all.py \
  --deliver telegram:CHAT_ID --prompt "$(cat reply-bot/watchdog_prompt.txt)"
```

Prompt refill & watchdog lengkap ada di [`docs/SCHEDULING.md`](SCHEDULING.md)
(salin apa adanya, ganti path kalau perlu).

> **Portabilitas:** semua script di repo ini sengaja **tidak** bergantung pada
> Hermes. Kalau mau pindah agent (Claude Code, Codex, GPT agent, dsb), lihat
> checklist di [`docs/PORTING.md`](PORTING.md).
