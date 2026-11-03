# threads-bot-panah (affiliate reply, POSTER HELD)

- Instance reply affiliate akun panah; replika dari threads-bot (blooply).
- Sesi: SALINAN PRIVAT dari sesi posting akun yang sama (cp -p, mtime dipertahankan). Bot reply blooply dan job posting TIDAK disentuh.
- Verifikasi sesi: check_login.py instance sendiri (LOGGED_IN True).
- Media gate: 1 jam ON / 3 jam OFF (WIB ON: 00, 04, 08, 12, 16, 20). Saat ON lampirkan foto produk yang direkomendasikan; saat OFF text + link saja; produk tanpa gambar = fallback text-only.
- Katalog: catalog/catalog.json (340 offer, komisi >=8%) + catalog/images/ (339 gambar).
- Keyword: scraper_keywords.json (115 grup: viral, intent rekomendasi, domain produk, nama akun besar).
- Session window: session.json duration_hours null (unlimited).
- STATUS: POSTER DITAHAN — daemon tidak dijalankan, job Hermes paused, sampai format balasan disepakati bersama Amad.
- Job Hermes (semua paused):
  - panah-scraper: id 63af158056fb
  - panah-auto-cycle: id 9adfa87339ee
  - panah-watchdog: id a07f31ac7236
- Aktivasi (hanya atas perintah Amad setelah format disepakati):
  1) Unpause job refill, lalu watchdog, lalu scraper.
  2) Jalankan daemon via systemd-run --user dengan unit instance.
  3) Verifikasi: antrean terisi, daemon hidup dengan cwd instance, dan 1 reply pertama dicek manual.
- Bila sesi kedaluwarsa: salin ulang file sesi posting akun yang sama ke state.json (cp -p, chmod 600), lalu verifikasi dengan check_login.py. Jangan pernah menjalankan login.py tanpa perintah pemilik.
- Catatan: kedua instance memakai file keyword yang sama, sehingga keduanya bisa membalas post yang sama dari akun berbeda (anti-double-reply hanya berlaku per instance). Putuskan saat aktivasi: pisah grup keyword per akun, atau stagger jadwal.

## Model v2 main_plus_extra (diport dari clove, 31 Okt 2026, otorisasi berdiri Amad 17:03 WIB)

- Balasan ke post utama WAJIB SELALU untuk setiap item (kecuali post itu sendiri masuk kategori skip).
- Balasan ke balasan atas hanya TAMBAHAN bila post ramai: jumlah balasan >= ambang di `top_reply_config.json` (default 20), dibaca poster SAAT POSTING, bisa diubah tanpa restart.
- Guard DILONGGARKAN: tidak ada lagi pembatalan `top_reply_changed`. Bila balasan atas berganti sejak refill, extra fallback ke balasan atas yang tampil saat posting.
- Extra di-skip SAJA bila balasan atas saat posting masuk kategori skip; balasan utama tetap jalan.
- Urutan: utama dulu, jeda manusiawi 60-120 detik (konfigurabel), lalu extra bila syarat terpenuhi.
- Dedup per bagian (utama = URL polos, extra = URL + `#top_reply`), retry per item, filter author 24 jam untuk keduanya, gate media ON/OFF untuk keduanya (extra tidak pernah membawa foto bila utama sudah melampirkan foto).
- Teks extra ditulis refill supaya tetap nyambung bila balasan atas berganti: berjangkar ke topik post, tanpa kutip detail spesifik balasan atas, tanpa menyebut nama akun balasan atas.
- Port: file `auto_comment.py`, `poster_daemon.py`, `merge_comments.py`, `fetch_top_reply.py`, `top_reply_config.json` disalin byte-identik dari implementasi v2 clove (hash terverifikasi sama); backup file lama di `backup-pre-v2/`. Verifikasi: py_compile lolos di venv instance, harness uji logika 40+ kasus ALL PASS atas salinan file panah, file state/session/keywords tidak berubah (hash sama dengan baseline). TIDAK ada posting live uji di panah sebelum aktivasi; posting pertama panah adalah balasan produksi yang diverifikasi manual saat aktivasi.

## AKTIVASI 31 Okt 2026 (otorisasi berdiri Amad 17:03 WIB)

- Status HELD BERAKHIR. Poster AKTIF: daemon poster HARUS jalan; watchdog merestart daemon bila monitor melaporkan daemon tidak jalan (perintah restart di bagian Tindakan watchdog).
- Format balasan final: persona revisi rencana §11 terpasang di prompt refill (clove hangat-praktis, panah ceria-berbagi).
- Keyword: scraper_keywords.json dipecah dua (clove 58 grup genap, panah 57 grup ganjil, tanpa irisan) supaya kedua akun tidak membalas post yang sama; backup asli di scraper_keywords.json.bak-pre-split.
- Model AI refill: agnes/agnes-2.5-flash via 9router-go, sama dengan job blooply.

UPDATE 31 Okt 2026 18:10 WIB atas perintah pemilik 18:09 WIB: aturan gaya baru, balasan affiliate memakai emoji relevan secukupnya, 1-2 per balasan, penempatan natural. Aturan ini dipasang ke prompt refill Hermes clove-auto-cycle dan panah-auto-cycle. TIDAK berlaku untuk bot blooply. Bridge darurat kini juga mengcover panah secara kondisional, hanya bila antrean panah kosong atau menipis atau refill Hermes-nya gagal, supaya tidak dobel dengan refill panah yang masih sehat.

UPDATE 31 Okt 2026 18:33-18:35 WIB atas perintah pemilik: (1) GATE MEDIA DIUBAH 1 jam ON / 2 jam OFF, jam ON WIB baru 00, 03, 06, 09, 12, 15, 18, 21 (sebelumnya 00/04/08/12/16/20). Diubah di auto_comment.py kedua instance (wib_hour % 4 menjadi % 3, backup auto_comment.py.bak-20261031-gate2h, uji logika 14/14 lolos di kedua instance). Karena gate ada di kode (bukan config), daemon lama tidak membaca jadwal baru sehingga KEDUA daemon di-restart bersih lewat unit systemd (panah PID baru 1107589, clove PID baru 1108056, masing-masing satu daemon, tanpa dobel). Blooply TIDAK disentuh (tetap teks saja via photo_disabled). (2) ATURAN GAYA ANTI-SLOP NAMA dipasang ke prompt refill kedua instance: jangan pernah membuka balasan dengan memanggil nama akun lawan bicara (utama maupun extra). File draf siaga dipindai: 0 pembuka nama ditemukan, tidak diubah untuk aturan ini.
