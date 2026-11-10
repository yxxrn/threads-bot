# Bot reply Threads

Kode bot yang membalas postingan Threads orang lain dari akun-akun yang
dikelola pemilik. Satu akun = satu instance (folder + 3 job Hermes +
daemon poster). Repo ini berisi KODE-nya saja; sesi login, antrean, dan
log runtime tidak pernah masuk repo.

## Dua mode

| Mode | Isi balasan | Dipakai akun |
| --- | --- | --- |
| `affiliate` | Balasan + satu link katalog Shopee (komisi >= 8%), kadang balasan extra ke balasan atas bila post ramai (>= 20 balasan), foto produk hanya di jam media gate | Model panah/clove |
| `text` | Balasan teks saja: reaksi nyambung + promosi halus tanpa link | Model blooply |

Aturan yang berlaku untuk semua mode: tanpa harga dalam bentuk apa pun,
tanpa menyebut nama akun lawan bicara di awal balasan, tanpa em-dash,
bahasa Indonesia, ramah dan tidak menyinggung, dan setiap balasan affiliate
wajib membawa link katalog (bila tidak ada produk yang nyambung, pakai
produk umum dengan transisi santai tanpa mengklaim nyambung).

## Struktur

```
src/                  Kode bersama semua mode dan semua akun:
                      guard identitas, verifikasi akun, antrean, pool,
                      scraper, monitor, cek sesi.
modes/affiliate/      Kode + konfigurasi khusus mode affiliate
                      (poster main+extra, merge v2, filter title-paste
                      dan anti-generik, katalog, top-reply).
modes/text/           Kode + konfigurasi khusus mode teks
                      (poster balasan tunggal, merge v1, tanpa foto).
bot-factory/          Perkakas pasang/lepas akun (lihat di bawah).
panah/ clove/         Sisa file bawaan repo lama (captions, compose_queue,
reply-bot/            repos, prompt, tools). BUKAN kode bot aktif: kode
                      bot sudah pindah ke src/ + modes/ sejak 2026-11-03.
api-experiment/       Perkakas API Threads terpisah (promo profil, dsb).
accounts/ autopost/   Perkakas lain yang sudah ada di repo ini.
docs/ migration/
```

Folder `panah/`, `clove/`, `reply-bot/` dulunya berisi salinan kode per
akun. Sejak restruktur 2026-11-03, kode hanya ada satu salinan (general)
di `src/` + `modes/`; yang tersisa di folder-folder itu hanyalah file
bawaan upstream yang tidak terkait kode poster. Jangan menambah kode baru
ke folder akun; tambah ke `src/` atau `modes/` lalu scaffold instance
baru dari sana.

## Tambah akun baru (bongkar pasang)

```bash
python3 bot-factory/new_bot.py --handle @namaakun --mode affiliate
python3 bot-factory/new_bot.py --handle @namaakun --mode text
```

Instance baru lahir dalam keadaan PARKIR (file `STOPPED` ada, job Hermes
nonaktif). Aktivasi wajib urut: pasang cookies akun itu sendiri ->
`verify_account.py` harus MATCH -> hapus `STOPPED` atas perintah pemilik
-> aktifkan job -> start daemon -> verifikasi post pertama. Detail dan
daftar yang masih perlu disesuaikan manual (persona, keyword, promo) ada
di `bot-factory/README.md` dan di `SETUP.md` tiap instance.

Lepas akun:

```bash
python3 bot-factory/remove_bot.py /home/agentuser/threads-bot-nama
```

Menghentikan daemon, menghapus job + script, dan mengarsipkan folder
instance (bukan menghapus permanen).

## Pengaman yang tidak bisa ditawar

- **Guard identitas** (`src/account_guard.py`): sebelum posting apa pun,
  daemon membuktikan akun yang login sama dengan `account.json` instance.
  Gagal (sesi salah, logout, atau tidak bisa ditentukan) = daemon keluar
  tanpa posting. Bukti sah hanya tautan profil di navigasi; tautan feed
  BUKAN bukti (insiden 2026-11-03: guard sempat terkecoh tautan feed).
- **STOPPED**: file ini berarti stop disengaja. Watchdog dilarang me-restart
  daemon selama STOPPED ada; STOPPED hanya boleh dihapus atas perintah
  eksplisit pemilik atau sesudah sesi baru lolos guard.
- **Sesi tidak pernah disalin antar instance.** Setiap sesi berasal dari
  cookies akun itu sendiri; setiap pemasangan wajib backup state lama dan
  lolos `verify_account.py`. File sesi tidak pernah di-commit
  (lihat `.gitignore`).
- **Sesi reply dicek di halaman post** (`src/check_reply_session.py`),
  bukan halaman home: cek home pernah melaporkan login padahal halaman
  post sudah menampilkan dinding login.

## Yang TIDAK ada di repo ini (sengaja)

- `state.json`, `storage_state*.json`, `cookies*.txt`, `session.json`:
  sesi login (rahasia dan kedaluwarsa). Sesi dipulihkan lewat prosedur
  refresh (cookies segar akun itu -> `verify_account.py` MATCH), bukan
  lewat git. Alternatif bila cookies tidak bisa didapat: login manual
  dengan username + password (`src/manual_login.py`, password ditanya saat
  runtime dan tidak pernah disimpan; bila muncul tantangan verifikasi/2FA,
  skrip berhenti dan pemilik yang menyelesaikan tantangannya).
- Antrean, log, histori post, screenshot debug, gambar katalog: data
  runtime, bukan kode. Gambar katalog bisa diregenerasi dari file
  affiliate links; `modes/affiliate/catalog.json` (daftar offer) ikut
  repo karena itu data publik katalog, bukan sesi.

## Status fleet

Status akun yang sedang jalan TIDAK ditulis di README ini (gampang basi;
README lama pernah mengklaim status yang sudah salah). Status live ada di
`session_meta.json` tiap instance di mesin vm-11.
