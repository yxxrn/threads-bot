# Penjadwalan & Integrasi

Bagian bot reply butuh 3 pekerjaan berulang. Autopost butuh penjadwalan
sederhana. Semua bisa dijalankan dengan 3 cara — pilih satu, jangan campur
(bisa double-post!).

## Tabel jadwal rekomendasi

| Pekerjaan | Interval | Jenis | Script |
|---|---|---|---|
| Reply: scrape post baru | 30 menit | no-agent (script) | `scraper_cycle.py` |
| Reply: refill antrean | 15 menit | **butuh LLM** | `build_pool.py` + `pick_drafts.py` + tulis komentar + `merge_comments.py` |
| Reply: watchdog | 30 menit | monitor (script cek + agent saat perlu) | `threads_monitor_all.py` |
| Reply: daemon poster | terus-menerus | daemon | `poster_daemon.py` |
| Autopost: promo Threads | 4 jam | no-agent | `promo_auto.py` |
| Autopost: promo X | 4 jam | no-agent | `x_promo_auto.py` |
| Autopost: muse X | tick 30 menit | no-agent (gating internal 90-120 menit) | `x_muse_auto.py` |
| Autopost: muse Threads | tick 30 menit | no-agent (gating internal 90-120 menit) | `p2_muse_auto.py` |

---

## Opsi 1: Hermes cron (dipakai di produksi)

Hermes adalah agent LLM + penjadwal. Keunggulannya: job "refill" bisa dikasih
**prompt** dan agent yang menulis komentarnya; watchdog bisa "monitor" (agent
hanya bangun saat output monitor berubah).

### 1a. Scraper (no-agent)

Wrapper `reply-bot/threads_scraper.sh`:

```bash
#!/bin/bash
set -euo pipefail
cd /path/ke/reply-bot
exec ./venv/bin/python scraper_cycle.py
```

Taruh di `~/.hermes/scripts/` lalu:

```bash
hermes cron create "every 30m" --name threads-scraper \
  --no-agent --script threads_scraper.sh
```

### 1b. Refill (agent + prompt)

Simpan prompt ini sebagai `~/.hermes/scripts/refill_prompt.txt` (ganti
`/path/ke/reply-bot` dan sesuaikan target queue), lalu:

```bash
hermes cron create "every 15m" --name threads-auto-cycle \
  --deliver telegram:CHAT_ID \
  --prompt "$(cat ~/.hermes/scripts/refill_prompt.txt)"
```

**Prompt refill (salin apa adanya):**

```text
Kamu menjalankan siklus REFILL CEPAT untuk Threads reply bot. Daemon poster
jalan terpisah (konsumsi ~22 post/jam) — tugasmu: pastikan antrian TIDAK
PERNAH KOSONG, dominasi post ID (target >=60% ID).

LANGKAH PERSIS (folder /path/ke/reply-bot, python: ./venv/bin/python):

1) `cd /path/ke/reply-bot && ./venv/bin/python queue_status.py`
   Output: `STATUS | 16 live (0 ID) | 12 tombstone | SESSION_OK`
   - NO_SESSION: jawab "Refill skip: tidak ada sesi." SELESAI.
   - live >= 12 DAN ID >= 10: jawab "Refill skip: antrian N live (X ID)." SELESAI.
   - Selain itu: LANJUT (prioritas ID mutlak).

2) `./venv/bin/python build_pool.py && ./venv/bin/python pick_drafts.py`
   → pick_drafts menulis candidates.json: 12 post siap draft.

3) Baca candidates.json. Untuk SETIAP kandidat, tulis komentar di
   comments_new.json: array [{url, author, lang, comment}]. ATURAN KOMEN:
   - Bahasa komen SAMA dengan bahasa post (id->Indonesia casual, en->English casual).
   - Kalimat 1 murni reaksi isi post (nyambung konteks, boleh topik apa saja).
     TIDAK BOLEH sebut produk.
   - Baris kosong, lalu kalimat 2 = promosi halus (AI pemotong video panjang
     jadi shorts, arahkan ke profil, tanpa link, no hard selling).
   - Natural manusia, tanpa em-dash. Variasikan promo (cek used_promos.txt).

4) `./venv/bin/python merge_comments.py`

5) Lapor 1-2 baris: N post baru (ID/EN), hasil queue_status.py terbaru.

PENTING: JANGAN jalankan auto_comment.py, JANGAN scrape (scraper terpisah
jalan tiap 30m), JANGAN pause cron, JANGAN trigger manual.
```

### 1c. Watchdog (monitor)

```bash
hermes cron create "every 30m" --name threads-watchdog \
  --monitor-script threads_monitor_all.py \
  --deliver telegram:CHAT_ID \
  --prompt "$(cat ~/.hermes/scripts/watchdog_prompt.txt)"
```

Prompt watchdog: lihat [`../reply-bot/WATCHDOG.md`](../reply-bot/WATCHDOG.md)
(salin isinya).

### 1d. Autopost

```bash
hermes cron create "every 4h" --name blooply-promo --no-agent \
  --script blooply-promo.sh --deliver telegram:CHAT_ID
```

Wrapper `~/.hermes/scripts/blooply-promo.sh`:

```bash
#!/bin/bash
set -e
cd /path/ke/autopost
exec .venv/bin/python promo_auto.py
```

### Catatan Hermes

- `--no-agent` = script dijalankan langsung, stdout dikirim apa adanya.
  Stdout kosong = silent (tidak kirim apa-apa) — cocok untuk script gating.
- `--monitor-script` = output script di-hash; agent hanya dijalankan kalau
  hash berubah. Script monitor **wajib deterministik** (tanpa timestamp!).
- Script diletakkan di `~/.hermes/scripts/` (bukan sembarang path).
- Job dan state ada di `~/.hermes/cron/jobs.json`; jangan diedit manual saat
  gateway jalan — pakai `hermes cron` CLI.

---

## Opsi 2: crontab murni

Tanpa agent: refill jadi "bangun pool saja", penulisan komentar dilakukan
script sendiri (`refill_cycle.py` — kamu tulis sendiri, panggil API LLM).

```cron
# ===== reply bot =====
*/30 * * * * cd $HOME/threads-bot/reply-bot && ./venv/bin/python scraper_cycle.py >> cron.log 2>&1
*/15 * * * * cd $HOME/threads-bot/reply-bot && ./venv/bin/python build_pool.py >> cron.log 2>&1 && ./venv/bin/python pick_drafts.py >> cron.log 2>&1 && ./venv/bin/python refill_cycle.py >> cron.log 2>&1 && ./venv/bin/python merge_comments.py >> cron.log 2>&1
*/30 * * * * cd $HOME/threads-bot/reply-bot && ./venv/bin/python threads_monitor_all.py >> cron.log 2>&1

# ===== autopost =====
0 */4 * * * cd $HOME/threads-bot/autopost && .venv/bin/python promo_auto.py >> cron.log 2>&1
0 */4 * * * cd $HOME/threads-bot/autopost && .venv/bin/python x_promo_auto.py >> cron.log 2>&1
*/30 * * * * cd $HOME/threads-bot/autopost && .venv/bin/python x_muse_auto.py >> cron.log 2>&1
```

Catatan:
- Cron pakai zona waktu server. Jadwal WIB = server CST → kurangi 1 jam
  (atau set `CRON_TZ=Asia/Jakarta` di atas file crontab).
- Daemon poster jangan dijadikan cron job — jalankan sekali sebagai service
  (systemd) atau nohup.
- `threads_monitor_all.py` di cron murni hanya mencetak alarm; kirim ke
  Telegram/Fonnte dsb. dengan `curl` kalau perlu.

---

## Opsi 3: systemd timer

Sama seperti opsi 2, tapi lebih rapi dan bisa lihat log via journalctl.
Contoh untuk 1 job (scraper):

`~/.config/systemd/user/threads-scraper.service`:

```ini
[Unit]
Description=Threads bot scraper cycle

[Service]
Type=oneshot
WorkingDirectory=%h/threads-bot/reply-bot
ExecStart=%h/threads-bot/reply-bot/venv/bin/python scraper_cycle.py
```

`~/.config/systemd/user/threads-scraper.timer`:

```ini
[Unit]
Description=Run threads scraper every 30 minutes

[Timer]
OnCalendar=*:0/30
Persistent=true
RandomizedDelaySec=120

[Install]
WantedBy=timers.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now threads-scraper.timer
systemctl --user list-timers | grep threads
```

Ulangi pola yang sama untuk job lain. Untuk daemon poster, jangan pakai timer —
buat `.service` biasa (`Restart=always`) atau `systemd-run` (lihat SETUP.md).

---

## Ganti agent? (Hermes → lain)

Semua bahan sudah portable. Yang perlu dipindah:

1. **Script & pipeline** — sudah tidak tergantung Hermes sama sekali
   (tidak ada import hermes, tidak ada hardcode path Hermes kecuali
   `threads_monitor_all.py` yang membaca
   `~/.hermes2/cron/jobs.json` — bagian itu opsional, bisa dihapus).
2. **Prompt refill** — teks murni, tinggal tempel di agent mana pun.
3. **Watchdog prompt** — teks murni.
4. **Penjadwal** — pakai cron/timer bawaan mesin.

Detail checklist: [`PORTING.md`](PORTING.md).
