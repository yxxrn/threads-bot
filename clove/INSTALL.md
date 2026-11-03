# threads-bot-clove (affiliate reply, POSTER HELD)

- Instance reply affiliate akun clove; replika dari threads-bot (blooply).
- Sesi: SALINAN PRIVAT dari sesi posting akun yang sama (cp -p, mtime dipertahankan). Bot reply blooply dan job posting TIDAK disentuh.
- Verifikasi sesi: check_login.py instance sendiri (LOGGED_IN True).
- Media gate: 1 jam ON / 3 jam OFF (WIB ON: 00, 04, 08, 12, 16, 20). Saat ON lampirkan foto produk yang direkomendasikan; saat OFF text + link saja; produk tanpa gambar = fallback text-only.
- Katalog: catalog/catalog.json (340 offer, komisi >=8%) + catalog/images/ (339 gambar).
- Keyword: scraper_keywords.json (115 grup: viral, intent rekomendasi, domain produk, nama akun besar).
- Session window: session.json duration_hours null (unlimited).
- STATUS: POSTER DITAHAN — daemon tidak dijalankan, job Hermes paused, sampai format balasan disepakati bersama Amad.
- Job Hermes (semua paused):
  - clove-scraper: id b35f2b215f2d
  - clove-auto-cycle: id 471587d5057e
  - clove-watchdog: id a329c388df0e
- Aktivasi (hanya atas perintah Amad setelah format disepakati):
  1) Unpause job refill, lalu watchdog, lalu scraper.
  2) Jalankan daemon via systemd-run --user dengan unit instance.
  3) Verifikasi: antrean terisi, daemon hidup dengan cwd instance, dan 1 reply pertama dicek manual.
- Bila sesi kedaluwarsa: salin ulang file sesi posting akun yang sama ke state.json (cp -p, chmod 600), lalu verifikasi dengan check_login.py. Jangan pernah menjalankan login.py tanpa perintah pemilik.
- Catatan: kedua instance memakai file keyword yang sama, sehingga keduanya bisa membalas post yang sama dari akun berbeda (anti-double-reply hanya berlaku per instance). Putuskan saat aktivasi: pisah grup keyword per akun, atau stagger jadwal.

## TOP-REPLY MODEL V2 (berlaku 2026-10-31, menggantikan model v1 post-XOR-top_reply)

- Model: balasan ke POST UTAMA WAJIB SELALU untuk setiap item (kecuali post itu sendiri masuk kategori skip, maka seluruh item di-skip seperti biasa). Balasan ke BALASAN ATAS hanya TAMBAHAN: bila post dirasa ramai, bot JUGA membalas balasan atasnya, sehingga satu post bisa mendapat dua balasan (utama + extra).
- Definisi ramai: jumlah balasan post >= ambang di `top_reply_config.json` (default 20), dibaca poster SAAT POSTING (bukan hanya saat refill). Ambang bisa diubah tanpa restart: edit file, daemon/poster membaca config fresh tiap item.
- Guard DILONGGARKAN untuk extra: tidak ada lagi pembatalan `top_reply_changed`. Bila balasan atas berganti sejak refill, extra tetap diposting ke BALASAN ATAS YANG TAMPIL SAAT POSTING (fallback ke balasan teratas saat itu), bukan dibatalkan. Teks extra ditulis refill supaya tetap nyambung bila balasan atas berganti: berjangkar ke topik post, tanpa kutip detail spesifik balasan atas, tanpa menyebut nama akun balasan atas.
- Extra di-skip SAJA (bukan seluruh item) bila balasan atas saat posting masuk kategori skip (spam, flame war, duka, romance spam, income bait, politik ekstrem, dsb.); balasan utama tetap jalan. Pengecekan kategori di poster memakai matcher konservatif di auto_comment.py (skip_category_of); refill tetap filter utama.
- Cara kerja targeting extra: halaman post dibuka, balasan pertama diidentifikasi dari urutan visual (koordinat y, bukan urutan DOM), lalu tombol balas MILIK balasan itu diklik (ikon balon percakapan, awalan path SVG `M12 3a9 9 0 0 0 0 18`; fallback tombol ke-2 grup 4 tombol action bar). Setelah klik, alur modal composer yang sama dipakai (foto, ketik, Post, verifikasi deep scan). Extra TIDAK PERNAH dialihkan ke post utama: bila tombol tidak ditemukan, extra gagal aman (no_top_reply_button, retryable); bila tidak ada balasan, extra di-skip.
- Urutan + jeda: utama dulu, jeda manusiawi 60-120 detik (konfigurabel extra_delay_min/max di top_reply_config.json), lalu extra bila syarat terpenuhi. Jeda ini di luar gap antar item daemon (110-135 detik).
- Media: gate 1 jam ON / 3 jam OFF berlaku untuk keduanya. Extra tidak pernah membawa foto bila balasan utama sudah melampirkan foto (tidak ada dua foto dalam satu thread); bila utama tidak melampirkan foto dan gate ON, extra boleh memakai media_path item.
- Filter author 24 jam berlaku untuk keduanya: balasan utama lewat pick_drafts (penulis post); extra dicek ulang poster saat posting terhadap penulis balasan atas saat itu (author_replied_24h dari posted_history.jsonl).
- Dedup per bagian: utama = URL polos, extra = URL + `#top_reply`, sehingga keduanya bisa hidup berdampingan. Retry per item (advance_item): utama gagal retryable atau extra gagal retryable membuat entri retry (maks 2 percobaan, lalu tombstone); utama ok + extra ok/skip-terminal membuat item selesai dan keluar dari retry.
- Format antrean v2: item membawa `comment` (utama, wajib) + `extra_comment` (opsional) + snapshot `top_reply` (konteks saja, bukan guard). merge_comments.py mendedup per bagian dan menggabungkan bagian dari URL yang sama dalam satu batch. Item v1 lama (target=top_reply, teks di comment) otomatis dikonversi jadi item extra-only oleh build_queue/merge.
- Deteksi read-only: `fetch_top_reply.py <url_post>` mencetak JSON berisi top_reply_url, top_reply_author, top_reply_text, reply_button, dan reply_count (jumlah permalink balasan yang ter-render; batas bawah karena virtualisasi). Dipakai refill untuk menulis extra_comment. Tidak posting, tidak menulis antrean.
- Config (`top_reply_config.json`, dibaca fresh tiap item): enabled, mode main_plus_extra/never, busy_threshold (default 20), skip_extra_on_skip_category (default true), extra_delay_min/max (default 60/120). Key lama mode auto/always = extra aktif, never = nonaktif; key lama skip_top_reply_on_skip_category dipakai bila key baru tidak ada.
- File yang diubah/ditambah (v2): auto_comment.py (count_replies, skip_category_of, author_replied_24h, decide_extra, post_extra_if_busy, post_item, advance_item, build_queue per bagian, main per bagian), poster_daemon.py (orkestrasi post_item + advance_item), merge_comments.py (dedup per bagian), fetch_top_reply.py (reply_count + docstring v2), top_reply_config.json (kunci baru).
- Status uji v2: py_compile semua file lolos; harness uji logika 40+ kasus lolos (utama selalu; extra hanya bila ramai; fallback ke balasan atas saat posting; skip-extra-saja; dedup utama+extra berdampingan; gate media pada keduanya; urutan + jeda; retry per bagian); dry run read-only pembacaan jumlah balasan: akumulasi href unik per langkah scroll terbukti (thread dupsy099: snapshot 8, akumulasi 47, BUSY). TES LIVE 2026-10-31 15:07 WIB (1 percobaan, thread dupsy099): GAGAL AMAN `no_expand_button`, 0 postingan, extra tidak dicoba (benar: utama gagal maka extra tidak dikejar). Penyebab: UI sesi bot berbahasa Mandarin (zh-Hans); tombol expand composer berlabel `展开编辑框`, tidak ada di selector kode (hanya Expand composer/Reply/Balas). Perbaikan yang diusulkan (belum diterapkan, menunggu perintah): tambahkan selector `[aria-label="展开编辑框"]` + fallback teks ke pembuka composer utama, lalu satu tes live ulang. Rantai dihentikan di sini sesuai perintah (tidak ada port panah, aktivasi, atau pemantauan).
- Panah: BELUM diterapkan pada ronde rework ini. Port ke panah hanya setelah clove dinyatakan stabil + ada perintah lanjutan pemilik.
- Riwayat v1 (2026-10-31 13:03-13:05 WIB): 2 percobaan live, 0 postingan, keduanya gagal aman (bug URL lalu guard top_reply_changed). Guard ketat v1 membuat item top_reply sering tombstone di thread aktif karena ranking balasan atas berubah tiap ~1 menit; v2 menjawab itu dengan fallback + extra opsional.

## AKTIVASI 31 Okt 2026 (otorisasi berdiri Amad 17:03 WIB)

- Status HELD BERAKHIR. Poster AKTIF: daemon poster HARUS jalan; watchdog merestart daemon bila monitor melaporkan daemon tidak jalan (perintah restart di bagian Tindakan watchdog).
- Format balasan final: persona revisi rencana §11 terpasang di prompt refill (clove hangat-praktis, panah ceria-berbagi).
- Keyword: scraper_keywords.json dipecah dua (clove 58 grup genap, panah 57 grup ganjil, tanpa irisan) supaya kedua akun tidak membalas post yang sama; backup asli di scraper_keywords.json.bak-pre-split.
- Model AI refill: agnes/agnes-2.5-flash via 9router-go, sama dengan job blooply.

UPDATE 31 Okt 2026 18:10 WIB atas perintah pemilik 18:09 WIB: aturan gaya baru, balasan affiliate memakai emoji relevan secukupnya, 1-2 per balasan, penempatan natural. Aturan ini dipasang ke prompt refill Hermes clove-auto-cycle dan panah-auto-cycle. TIDAK berlaku untuk bot blooply. Bridge darurat kini juga mengcover panah secara kondisional, hanya bila antrean panah kosong atau menipis atau refill Hermes-nya gagal, supaya tidak dobel dengan refill panah yang masih sehat.

UPDATE 31 Okt 2026 18:33-18:35 WIB atas perintah pemilik: (1) GATE MEDIA DIUBAH 1 jam ON / 2 jam OFF, jam ON WIB baru 00, 03, 06, 09, 12, 15, 18, 21 (sebelumnya 00/04/08/12/16/20). Diubah di auto_comment.py kedua instance (wib_hour % 4 menjadi % 3, backup auto_comment.py.bak-20261031-gate2h, uji logika 14/14 lolos di kedua instance). Karena gate ada di kode (bukan config), daemon lama tidak membaca jadwal baru sehingga KEDUA daemon di-restart bersih lewat unit systemd (panah PID baru 1107589, clove PID baru 1108056, masing-masing satu daemon, tanpa dobel). Blooply TIDAK disentuh (tetap teks saja via photo_disabled). (2) ATURAN GAYA ANTI-SLOP NAMA dipasang ke prompt refill kedua instance: jangan pernah membuka balasan dengan memanggil nama akun lawan bicara (utama maupun extra). File draf siaga dipindai: 0 pembuka nama ditemukan, tidak diubah untuk aturan ini.
