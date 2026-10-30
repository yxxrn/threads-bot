# Migrasi mesin (mati / pindah VPS)

Dua script, satu alur. Tujuannya: kalau mesin bot mati, pindah ke mesin lain
di tailnet tanpa mengulang setup manual dan **tanpa kehilangan state**.

| Script | Dijalankan di | Fungsi |
|---|---|---|
| `threads-bot-export-state.sh` | mesin **sumber** (yang botnya masih hidup) | bungkus semua state runtime jadi satu `.tar.gz` |
| `threads-bot-migrate.sh` | mesin **sumber** (punya SSH ke target) | pasang kode + venv + provider + 5 job Hermes; `--state` sekalian pulihkan state |

## Kenapa perlu

Repo ini sudah *portable* (lihat `docs/PORTING.md`), tapi yang **tidak** ada di
git adalah justru bagian paling mahal: antrean, tombstone, `replied_urls.json`
(penjaga double-reply), `posted_history.jsonl`, cookies, counter promo, dan
media yang di-hardcode path-nya. Hilang = mulai dari nol, dan berisiko
reply ganda ke post lama.

## Alur normal: pindah mesin

```bash
# 1. di mesin sumber — bungkus state
./migration/threads-bot-export-state.sh
#    -> /tmp/threads-bot-state-<ts>.tar.gz

# 2. dari mesin sumber — pasang di target
./migration/threads-bot-migrate.sh 100.84.135.121 \
    --state /tmp/threads-bot-state-<ts>.tar.gz
```

`--state` melakukan INSTALL + RESTORE. Tanpa `--state` hanya INSTALL (mesin
baru, state kosong, tunggu cookies baru).

Opsi lain:

```bash
--user ubuntu     # user SSH (default ubuntu)
--no-cron         # jangan sentuh Hermes cron (mis. target dipakai untuk hal lain)
--resume-all      # blooply-promo & clove-post langsung aktif
                  # (default: paused kalau variants.json / clove_queue.json belum ada)
```

## Kalau mesin sumber SUDAH mati

State tidak bisa diekspor lagi. Yang masih bisa:

1. `./migration/threads-bot-migrate.sh <target>` — kode, venv, provider, job.
2. Kirim cookies Threads baru (satu-satunya yang wajib dari kamu).
3. **Wajib**: batasi `SCRAPER_MAX_AGE` supaya tidak menyapa post lama.
   ```bash
   # di target, ~/.hermes/scripts/threads_scraper.sh memakai:
   #   --max-age-hours "${SCRAPER_MAX_AGE:-168}"
   # set 24 dulu selama 1-2 hari, lalu naikkan lagi
   ```
   `replied_urls.json` hilang artinya bot tidak tahu post mana yang sudah
   dijawab. Antrean baru + jendela 24 jam = risiko minimum.

## Yang dilakukan `migrate.sh` (8 langkah, idempoten)

1. cek prasyarat (sudo, python3, git, rsync)
2. clone repo -> `/home/agentuser/threads-bot`, `threads-bot-repo/api-experiment`,
   `autopost`, `threads-bot-docs`; **tidak menimpa** file yang sudah ada
3. venv reply-bot (`cloakbrowser`, `playwright`) + cek chromium
4. venv API path (`curl_cffi`, `Pillow`) + import `api_client`
5. provider `9router-go` (+ entri `agnes/*`) di `~/.hermes/config.yaml`,
   key diambil dari config mesin sumber, backup otomatis
6. restore state dari `--state` (file & folder, `chmod 600` untuk cookie)
7. tulis 4 wrapper di `~/.hermes/scripts/` + daftar 5 job Hermes
8. verifikasi: python, provider, `queue_status.py`, output monitor

Job yang dibuat:

| Job | Jadwal | Mode |
|---|---|---|
| `threads-scraper` | 30m | no-agent (`scraper_cycle.py`) |
| `threads-auto-cycle` | 15m | agent, `agnes/agnes-2.5-flash` @ `9router-go` |
| `threads-watchdog` | 30m | monitor (`threads_monitor_all.sh`) |
| `blooply-promo` | 240m | no-agent, **paused** sampai `variants.json` ada |
| `clove-post` | 15m | no-agent, **paused** sampai `clove_queue.json` ada |

Job yang sudah ada dilewati (dicocokkan lewat nama), jadi aman dijalankan
ulang setelah perbaikan.

## Sisa langkah manual setelah migrate

```bash
# di target, sebagai agentuser
cd ~/threads-bot
./venv/bin/python check_login.py          # setelah cookies baru dipasang

# mulai sesi (duration_hours: null = jalan terus)
./venv/bin/python - <<'PY'
import json, datetime
json.dump({"started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "duration_hours": None}, open("session.json", "w"), indent=1)
PY

# daemon poster: systemd user unit, JANGAN nohup dari dalam cron
systemd-run --user --unit=threads-poster-daemon --collect \
  --working-directory=$PWD $PWD/venv/bin/python $PWD/poster_daemon.py
```

Kalau `variants.json` / `clove_queue.json` sudah dipulihkan:

```bash
hermes cron resume <id-blooply-promo>
hermes cron resume <id-clove-post>
```

## Jebakan yang sudah ditangani

- **Path hardcoded** `clove_runner_api.py` & `blooply_promo_api.py`
  (`/home/agentuser/...`) -> migrate memakai layout yang sama persis, jadi
  tidak perlu patch kode.
- **`daemon.log` pakai UTC**, jam mesin CST (UTC+8). Membandingkan keduanya
  langsung bikin kesimpulan "cooldown 8 jam" padahal 14 menit.
- **Daemon mati saat cron selesai** kalau dijalankan `nohup` dari dalam run
  cron -> pakai `systemd-run --user`, sudah ada di `WATCHDOG.md`.
- **Monitor output harus deterministik** (tanpa timestamp), kalau tidak agent
  watchdog bangun tiap tick.
- **Lock files tidak diekspor** supaya mesin tujuan tidak mengira ada proses
  lain yang sedang jalan.
- **`jobs.json` Hermes hanya untuk referensi**; job didaftarkan ulang lewat
  `hermes cron create` supaya id dan path-nya benar untuk mesin baru.