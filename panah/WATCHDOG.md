# Watchdog threads-bot-panah (affiliate reply, POSTER HELD)

## ATURAN STOP SENGAJA (2026-11-03)

Bila file STOPPED ada di folder instance ini, daemon poster yang TIDAK jalan adalah kondisi yang disengaja, BUKAN masalah: JANGAN restart, catat saja, laporkan 'intentionally stopped'. File STOPPED hanya boleh dihapus atas perintah eksplisit pemilik, atau saat sesi baru akun ini dipasang dan guard identitas (account_guard.py) lolos.

Instance: /home/agentuser/threads-bot-panah
Akun: @panah (lihat check_login.py untuk handle terverifikasi)
Refill job: 9adfa87339ee (PAUSED selama held)
Daemon unit (JANGAN dijalankan selama held): threads-poster-daemon-panah

## Status HELD

Daemon poster sengaja TIDAK dijalankan dan semua job Hermes instance ini PAUSED, sampai format balasan disepakati bersama pemilik. Laporan monitor "daemon poster TIDAK jalan" adalah kondisi yang diharapkan selama held.

## Tindakan watchdog

1. Daemon poster TIDAK jalan -> SELAMA HELD: jangan restart, catat saja. Setelah aktivasi: restart via systemd user unit:
   systemd-run --user --unit=threads-poster-daemon-panah --collect \
     --working-directory=/home/agentuser/threads-bot-panah \
     /home/agentuser/threads-bot-panah/venv/bin/python /home/agentuser/threads-bot-panah/poster_daemon.py
   Verifikasi dengan proses yang cwd-nya == /home/agentuser/threads-bot-panah.
2. Sesi habis/tidak ada -> JANGAN posting; lapor sesi berakhir.
3. Reply gagal beruntun -> diagnosa auto_log.json + shots/err_ terbaru; perbaiki auto_comment.py bila ada bug jelas; tes 1 post dari retry_queue.json (hanya setelah aktivasi).
4. Cron stuck >45 menit -> kill worker stuck, trigger ulang job refill.
5. Cron paused padahal sesi aktif -> SELAMA HELD: jangan resume; setelah aktivasi: resume job refill.
6. Sesi browser >25 hari -> ingatkan pemilik siapkan sesi baru (salin ulang dari sesi posting akun yang sama).
7. False alarm -> jawab "Watchdog: tidak ada masalah."

JANGAN pause cron refill kecuali sesi habis. JANGAN posting manual lebih dari 2 reply per pemulihan (setelah aktivasi).

## AKTIVASI 31 Okt 2026 (otorisasi berdiri Amad 17:03 WIB)

- Status HELD BERAKHIR. Poster AKTIF: daemon poster HARUS jalan; watchdog merestart daemon bila monitor melaporkan daemon tidak jalan (perintah restart di bagian Tindakan watchdog).
- Format balasan final: persona revisi rencana §11 terpasang di prompt refill (clove hangat-praktis, panah ceria-berbagi).
- Keyword: scraper_keywords.json dipecah dua (clove 58 grup genap, panah 57 grup ganjil, tanpa irisan) supaya kedua akun tidak membalas post yang sama; backup asli di scraper_keywords.json.bak-pre-split.
- Model AI refill: agnes/agnes-2.5-flash via 9router-go, sama dengan job blooply.
