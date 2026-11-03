# Threads bots backup (code only)

Snapshot: 2026-11-02. Repo ini berisi KODE bot reply Threads Blooply/Clove/Panah
dan promo profil Blooply di vm-11. Dibuat agar perbaikan tidak hilang bila mesin
diganti/dibangun ulang.

## Yang TIDAK ada di repo ini (sengaja)
- state.json, storage_state*.json, cookies*.txt, session.json: berisi sesi login
  (RAHASIA, dan kedaluwarsa). Jangan pernah di-commit. Sesi dipulihkan lewat
  prosedur refresh di bawah, bukan lewat git.
- *.log, posted_history.jsonl, comments*.json, candidates*.json, found_posts*.json:
  data operasional runtime, bukan kode.
- catalog/: 339 gambar produk, regenerable dari file affiliate links.
- shots/: screenshot debugging.

## Perbaikan penting yang tersimpan di sini
- 2026-11-01: anti-generik guard (is_generic_reaction) di merge_comments.py dan
  auto_comment.py clove+panah; LINK-ALL defense di post_item; perbaikan NameError
  (import re eksplisit); persona + ATURAN ANTI-GENERIK di prompt refill.
- 2026-11-02: diagnosis login wall (lihat bawah) + check_reply_session.py.

## Prosedur refresh sesi reply (terbukti 2026-11-02)
1. Minta cookies segar dari pemegang akun (format Netscape dari Cookie-Editor).
2. Konversi ke format Playwright storage_state (strip quotes, decode octal \054
   jadi koma, %3A dipertahankan seperti file lama) -> tulis ke state.json instance
   (backup dulu: state.json.bak-YYYYMMDD-HHMM). Verifikasi: 8 nama cookie sama,
   ds_user_id sama dengan file lama (perbandingan boolean saja).
3. Restart daemon (systemd-run --user --unit=threads-poster-<nama> ...).
4. Verifikasi 2 OK berturut di daemon.log sebelum menyatakan beres.

## Pelajaran login wall (2026-11-02)
Gejala no_expand_button 100% selama 1 jam ternyata sesi browser SUDAH LOGOUT:
klik Reply memunculkan dinding "Say more with Threads", bukan composer.
check_login.py yang hanya mengecek halaman home memberi FALSE POSITIVE
(LOGGED_IN True padahal halaman post menunjukkan dinding login).
Verifikasi sesi reply WAJIB di halaman post: jalankan check_reply_session.py
dengan satu URL post antrean; verdict LOGIN_WALL berarti sesi mati.

## Push ke GitHub (belum dilakukan, butuh repo + deploy key)
1. Buat repo privat kosong di GitHub.
2. Tambahkan public key ~/.ssh/id_github_bots.pub sebagai Deploy key (write access).
3. git remote add origin <url> && git push -u origin main

## Insiden 2026-11-03 + guard identitas akun

Pada 2 Nov 2026, transplantasi cookies blooply ikut tersalin ke state.json
panah (mtime identik, ds_user_id identik). Akibatnya 206 post affiliate
panah (2 Nov 19:30 WIB s.d. 3 Nov 09:12 WIB) terbit sebagai @blooplyy_.
Perbaikan 3 Nov 2026 (commit ini):
- `account_guard.py` + `verify_account.py` di tiap instance: sebelum posting
  apa pun, daemon WAJIB membuktikan sesi yang login == handle di `account.json`
  (baca tautan profil di navigasi home). Gagal = daemon keluar, tidak posting.
- `account.json` (handle yang ditugaskan) + `session_meta.json` (metadata sesi,
  tanpa secret) di tiap instance.
- Daemon menolak jalan bila file `STOPPED` ada (stop disengaja yang ditaati
  watchdog; menghapus STOPPED hanya atas perintah eksplisit pemilik).
- Prompt + playbook watchdog (WATCHDOG.md) diperbarui: file STOPPED berarti
  daemon yang tidak jalan BUKAN masalah dan JANGAN di-restart.
- Aturan sesi: JANGAN PERNAH menyalin state.json antar instance. Sesi tiap
  akun hanya berasal dari cookies akun itu sendiri; setiap pemasangan sesi
  wajib membackup state.json lama dan lolos `verify_account.py`.
- Status 3 Nov 2026: blooply jalan lagi (guard lolos); panah STOPPED (sesi
  asli tertimpa, menunggu cookies segar akun panah); clove STOPPED (akun
  tersuspend 1 Nov 2026).

Penyempurnaan guard 2026-11-03 (siang): tautan feed BUKAN bukti login. Guard awal sempat terkecoh tautan feed saat sesi blooply sudah logout (false MATCH); setelah diperketat, sesi logout terdeteksi sebagai UNDETERMINED/feed-only dan daemon menolak jalan. Hanya tautan profil navigasi (aria-profile/nav) yang dihitung sebagai bukti login.
