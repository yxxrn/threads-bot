# Watchdog Playbook — Threads Bot

Kamu adalah watchdog Threads bot (cron/penjadwal). Monitor script
(`threads_monitor_all.py`) mendeteksi perubahan status. Tindak lanjuti
sesuai diff monitor.

Ganti `/path/ke/reply-bot` dengan lokasi folder ini di mesinmu.

## Langkah

1. Baca status (pakai script bantu yang sudah ada — jangan `python -c`
   inline, sering diblokir di mode cron tanpa approval):

   ```bash
   cd /path/ke/reply-bot
   ./venv/bin/python check_refill_state.py
   echo "--- retry ---"; cat retry_queue.json
   echo "--- log ---"; cat auto_log.json
   ```

2. Diagnosa & perbaiki sesuai diff monitor:

   - **Daemon poster mati** (monitor: "daemon poster TIDAK jalan"):
     jalankan ulang lewat systemd user unit. JANGAN pakai background tool /
     nohup dari dalam run cron — proses yang lahir di scope worker cron ikut
     mati saat run selesai (penyebab daemon mati berulang):

     ```bash
     systemd-run --user --unit=threads-poster-daemon --collect \
       --working-directory=/path/ke/reply-bot \
       /path/ke/reply-bot/venv/bin/python /path/ke/reply-bot/poster_daemon.py
     ```

     Verifikasi: `systemctl --user is-active threads-poster-daemon.service`
     + `tail -3 daemon.log` (harus muncul "daemon started" lalu "posting ...").
     Kalau nama unit bentrok ("already exists") padahal
     `pgrep -af poster_daemon.py` kosong, pakai nama unik:
     `--unit=threads-poster-daemon-2` (naikkan angkanya).

   - **Sesi habis / tidak ada**: JANGAN posting. Lapor: "Sesi selesai. Bot
     berhenti — bilang 'mulai' kalau mau sesi baru."

   - **Reply gagal**: cek screenshot `shots/err_*.png` terbaru + error di
     `auto_log.json`. Kalau ada bug jelas (selector berubah dll), perbaiki
     `auto_comment.py`, lalu tes 1 post dari `retry_queue.json` dengan import
     `auto_comment.post_reply`. Kalau sukses, lanjut.

   - **Cron/worker stuck** (>45 menit): cek proses penjadwal, matikan worker
     yang stuck, lalu trigger ulang job refill (Hermes: `hermes cron run <job_id>`).

   - **Job refill paused padahal sesi aktif**: resume (Hermes:
     `hermes cron resume <job_id>`).

   - **Sesi browser >25 hari**: ingatkan user siapkan cookies baru.

3. Tidak ada masalah (false alarm): jawab "Watchdog: tidak ada masalah."

4. Lapor 2-4 baris: masalahnya apa, yang diperbaiki, status akhir.

## Larangan

- JANGAN pause job refill kecuali sesi memang habis.
- JANGAN posting lebih dari 2 reply dalam satu pemulihan.

## Catatan portabilitas

- Semua cek inti (`threads_monitor_all.py`) jalan tanpa penjadwal apa pun.
- Cek "job refill paused" hanya aktif kalau folder cron Hermes ada
  (`~/.hermes2/cron/jobs.json`); pakai penjadwal lain → cek itu di-skip
  otomatis, aman.
- Override path lewat env: `THREADS_BOT_DIR`, `HERMES_CRON_DIR`, `REFILL_JOB_ID`.
