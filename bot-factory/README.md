# bot-factory: pasang dan lepas akun bot reply Threads

Satu akun = satu folder instance (`threads-bot-<slug>`) + 3 job Hermes
(scraper, auto-cycle/refill, watchdog) + 2 script Hermes + 1 unit daemon.
Factory membuat dan melepas paket itu dari kode general (`src/` +
`modes/<mode>/`), tanpa menyentuh instance lain.

## Tambah akun

```bash
python3 bot-factory/new_bot.py --handle @namaakun --mode affiliate
python3 bot-factory/new_bot.py --handle @namaakun --mode text
```

Mode:

- `affiliate`: balasan bawa link katalog (model panah/clove). Ada balasan
  extra ke balasan atas (post ramai), media gate, filter title-paste dan
  anti-generik.
- `text`: balasan teks saja (model blooply). Tanpa link produk.

Yang dibuat factory (semua di mesin vm-11, user `agentuser`):

- Folder instance dari kode general + `account.json`, `session_meta.json`,
  `WATCHDOG.md`, `SETUP.md`, `factory.json` (manifest job/script/unit).
- File `STOPPED` (parkir bawaan): daemon menolak jalan sampai STOPPED
  dihapus atas perintah eksplisit pemilik.
- Antrean kosong (`comments.json`, `comments_new.json`,
  `replied_urls.json`) + folder `shots/`.
- Symlink `venv/` ke venv instance template (affiliate: panah, text:
  blooply) dan, untuk affiliate, symlink `catalog/images/` ke katalog panah.
- Draf job (`jobs-draft.json`) dan draf script (`scripts-draft/`).
  Tanpa `--apply-jobs`, TIDAK ADA yang ditulis ke `jobs.json` Hermes.
- Dengan `--apply-jobs`, 3 job ditulis ke `jobs.json` dalam keadaan
  NONAKTIF (`enabled=false`, backup dibuat dulu) dan 2 script dipasang.

## Aktivasi (wajib urut)

1. Pasang sesi dari cookies akun itu sendiri ke `state.json` instance
   (backup dulu bila ada). JANGAN PERNAH menyalin `state.json` dari
   instance lain. Di langkah yang sama, refresh `session.json` instance:
   `started_at` = waktu pemasangan (ISO UTC), `duration_hours` = null
   (factory menulis placeholder saat scaffold; tanpa refresh, umur sesi
   yang tercatat adalah umur scaffold, bukan umur sesi).
2. `venv/bin/python verify_account.py` harus mencetak MATCH.
3. Hapus `STOPPED` hanya atas perintah eksplisit pemilik.
4. Aktifkan 3 job, start daemon (perintah lengkap ada di `SETUP.md`
   instance), lalu verifikasi post pertama OK sebagai akun yang benar.

## Yang masih template dan wajib disesuaikan

- Persona prompt refill (affiliate memakai persona panah sebagai awal).
- Keyword scraper: disalin dari template. Bila akun baru jalan bersamaan
  dengan akun template, pisahkan keyword dulu (nol tumpang tindih). Bila
  akun baru menggantikan akun template, keyword boleh dipakai apa adanya.
- Promo halus (text memakai promosi Blooply sebagai awal): ganti dengan
  produk/layanan akun baru.
- Gambar katalog affiliate menumpang katalog panah (symlink). Bila katalog
  panah diarsipkan, arahkan ulang symlinknya.

## Lepas akun

```bash
python3 bot-factory/remove_bot.py /home/agentuser/threads-bot-nama
```

Menghentikan unit, menghapus 3 job + 2 script (backup `jobs.json` dulu),
lalu MEMINDAHKAN folder instance ke `bots-archive/<slug>-<waktu>/`.
Tidak ada yang dihapus permanen. Instance warisan (blooply, panah, clove)
tidak punya `factory.json` dan ditolak kecuali `--force` disertai
`--job-ids` dan `--scripts` eksplisit.

## Keamanan yang tidak bisa ditawar

- Guard identitas (`account_guard.py`): daemon membuktikan sesi yang login
  sama dengan `account.json` di SETIAP konteks browser; gagal = keluar,
  tidak posting. Bukti sah hanya tautan profil navigasi; tautan feed
  ditolak (pelajaran insiden 2026-11-03).
- Sesi reply wajib dicek di halaman post (`check_reply_session.py`),
  bukan halaman home (cek home pernah memberi false positive).
- File sesi (`state.json`, `storage_state*.json`, cookies, `session.json`)
  TIDAK PERNAH masuk repo (lihat `.gitignore`).
