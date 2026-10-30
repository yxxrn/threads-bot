# Akun & job — satu peta, satu CLI

Semua akun Threads terdaftar di `registry.json`. Tidak ada path yang
ditanam di dalam script job: kalau pindah mesin atau ganti nama folder,
cukup edit satu file ini.

## Isi registry

| Field | Arti |
|---|---|
| `role` | `reply` (daemon komentar), `promo` (post promo berkala), `queue` (antrean post), `idle` |
| `dir` | folder kerja runner |
| `runner` | script Python yang dipanggil untuk posting |
| `python` | interpreter yang dipakai runner (venv masing-masing) |
| `state` | file cookies Playwright akun itu |
| `queue` | file antrean (kalau ada) |
| `job` | ID job Hermes yang menjalankan runner |
| `schedule` | jadwal job (informatif) |

Akun yang terdaftar sekarang: `reply` (blooply utama), `blooply` (promo),
`clove` (antrean tutorial + repo), `panah` (antrean repo akun ketiga).

## Perintah

```bash
cd ~/accounts
./account.py list                 # semua akun: job, sesi, antrean
./account.py status clove         # detail satu akun
./account.py check clove          # cek cookie masih login (OK/EXPIRED)
./account.py pause blooply        # hentikan job akun itu
./account.py resume blooply       # lanjutkan lagi
./account.py post-next clove      # paksa post satu item sekarang
```

`post-next` menolak role `reply` — daemon komentar punya alurnya sendiri.

## Pindah mesin

1. `git clone` repo ini, lalu copy folder `~/.hermes/cron/` kalau job mau ikut.
2. Copy file state (JANGAN dari git):
   `~/.hermes/cron/jobs.json`, `~/.hermes/cron/executions.db`,
   `~/threads-bot/state.json`, `~/threads-playwright/storage_state*.json`,
   `~/clove/clove_queue.json`, `~/clove/queue_state.json`,
   `~/blooply_promo/variants.json`, `~/blooply_promo/promo_state.json`,
   plus folder media yang dirujuk antrean.
3. Kalau username/venv beda, edit `registry.json` (semua path pakai `~`).
4. `./account.py list` — sesi harus `OK`, antrean kebaca.
5. `./account.py resume <akun>` untuk job yang mau dijalankan.

## Tambah akun baru

1. Copy `storage_state` akun baru ke `~/threads-playwright/storage_state_<nama>.json`.
2. Siapkan folder kerja + runner (bisa pakai `clove_runner_api.py` sebagai basis).
3. Tambah entri di `registry.json` dengan `role`, `dir`, `runner`, `python`, `state`.
4. Buat job Hermes yang memanggil runner itu, lalu isi `job` dengan ID-nya.
5. `./account.py check <nama>` sampai `OK`, baru `resume`.

## Job yang jalan

| Job | Akun | Jadwal | Script |
|---|---|---|---|
| reply daemon | reply | terus-menerus | `~/threads-bot/poster_daemon.py` |
| refill komentar | reply | tiap 20m | `~/threads-bot/scraper_cycle.py` |
| clove-post | clove | tiap 15m | `~/clove-post.sh` |
| panah-post | panah | tiap 15m | `~/.hermes/scripts/panah-post.sh` |
| blooply-promo | blooply | tiap 240m | `~/blooply_promo/blooply_promo.sh` |

Job-nya sendiri tetap dipegang Hermes (`hermes cron list`), tapi ID-nya
tercatat di registry supaya tidak perlu hafal.
