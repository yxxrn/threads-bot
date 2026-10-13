# Portabilitas — Jalanin dengan agent lain

Dokumen ini untuk siapa pun yang mau menjalankan repo ini dengan **agent
selain Hermes** (Claude Code, Codex, Cursor, Gemini CLI, bot sendiri, dsb.)
atau tanpa agent sama sekali. Tujuannya: tidak ada kejutan, tidak ada
ketergantungan tersembunyi.

## TL;DR — apa yang agent-butuhkan

| Kebutuhan | Di repo ini | Catatan portabilitas |
|---|---|---|
| Browser otomasi | Playwright + CloakBrowser | Murni Python, jalan di agent mana pun |
| Penulis komentar (LLM) | Prompt teks di `docs/SCHEDULING.md` | Tempel ke agent apa pun |
| Penjadwal | Tidak dibundel | Pakai cron/systemd/Hermes — pilih sendiri |
| Notifikasi | Tidak dibundel | Kirim stdout ke Telegram/email sendiri |
| Session | File JSON (`state.json` dll.) | Pindah mesin = copy file-nya |

**Tidak ada** import `hermes`, tidak ada SDK khusus, tidak ada daemon pihak
ketiga. Yang ada hanya Python + Playwright + file JSON.

---

## Checklist pindah ke agent/mesin baru

### 1. Pindahkan kode

```bash
git clone https://github.com/yxxrn/threads-bot
cd threads-bot
```

### 2. Pindahkan file state (JANGAN dari git — file ini di-gitignore)

Copy manual dari mesin lama (via scp/USB), daftar lengkap:

**autopost:**
```
autopost/storage_state.json        (Threads utama)
autopost/storage_state_p3.json     (Threads akun kedua — kalau ada)
autopost/storage_state_x.json      (X)
autopost/storage_state_fb.json     (FB — kalau dipakai)
autopost/.promo_state.json         (counter hook promo)
autopost/.x_muse_state.json        (counter muse X)
autopost/.p2_muse_state.json       (counter muse Threads)
autopost/media/*                   (gambar promo — kalau tidak mau ganti)
```

**reply-bot:**
```
reply-bot/state.json               (cookies Threads bot)
reply-bot/session.json             (jendela sesi aktif)
reply-bot/comments.json            (antrean — opsional, bisa dibangun ulang)
reply-bot/retry_queue.json         (tombstone — PENTING, jangan hilang)
reply-bot/replied_urls.json        (PENTING — tanpa ini bisa double-reply!)
reply-bot/posted_history.jsonl     (PENTING — filter author 24 jam)
reply-bot/skip_urls.txt            (daftar URL dilarang)
reply-bot/used_promos.txt          (riwayat variasi promo)
reply-bot/scraper_keywords.json    (sudah ada di repo — cek tidak ketinggalan)
```

> ⚠️ **Kalau `replied_urls.json` dan `posted_history.jsonl` hilang** → bot
> bisa membalas post yang sama dua kali. Kalau tidak bisa dipindah, mulai
> sesi baru dengan queue kosong, jangan pakai pool lama.

### 3. Install dependensi

```bash
# autopost
cd autopost && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# reply-bot
cd ../reply-bot && python3 -m venv venv && ./venv/bin/pip install cloakbrowser==0.5.11 playwright==1.63.0
```

### 4. Tes tanpa agent (semua script harus jalan standalone)

```bash
# autopost — dry run: cek login
cd autopost && .venv/bin/python -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    c = b.new_context(storage_state='storage_state.json')
    pg = c.new_page(); pg.goto('https://www.threads.com/', wait_until='domcontentloaded')
    print('URL:', pg.url, '| login page?', 'login' in pg.url)
    b.close()"

# reply-bot — cek session
cd ../reply-bot && ./venv/bin/python check_login.py
./venv/bin/python queue_status.py
./venv/bin/python scraper_cycle.py --groups 1 --limit 5   # tes scrape kecil
```

Semua harus jalan **tanpa agent**. Kalau ada yang butuh agent, itu bug —
laporkan.

### 5. Sambungkan penjadwal pilihanmu

Lihat `docs/SCHEDULING.md` — tiga opsi lengkap dengan contoh file.
Yang perlu dijadwalkan:

| Job | Frekuensi | Butuh LLM? |
|---|---|---|
| `scraper_cycle.py` | 30 menit | Tidak |
| `build_pool.py` + `pick_drafts.py` | 15 menit | Tidak |
| Tulis komentar → `comments_new.json` | 15 menit | **Ya** |
| `merge_comments.py` | setelah tulis | Tidak |
| `threads_monitor_all.py` | 30 menit | Tidak |
| `poster_daemon.py` | daemon (sekali jalan) | Tidak |
| Autopost (promo/muse) | 4 jam / 30 menit | Tidak |

### 6. Sambungkan penulis komentar dengan agent pilihanmu

Prompt lengkap ada di `docs/SCHEDULING.md` bagian "Refill (agent + prompt)".
Adaptasi per agent:

| Agent | Cara masang |
|---|---|
| **Hermes** | `hermes cron create ... --prompt "$(cat prompt.txt)"` |
| **Claude Code / Codex / Cursor** | Taruh prompt sebagai instruksi task; jadwalkan CLI-nya lewat cron: `claude -p "$(cat prompt.txt)"` |
| **Bot sendiri** | Panggil API LLM (OpenAI-compatible) dari script; prompt sama |
| **Tanpa agent** | Tulis `refill_cycle.py` — panggil API LLM langsung, contoh struktur di bawah |

**Struktur `refill_cycle.py` (tanpa agent):**

```python
#!/usr/bin/env python3
"""Contoh penulis komentar tanpa agent — panggil API LLM sendiri."""
import json, subprocess, urllib.request
from pathlib import Path

BOT = Path(__file__).resolve().parent
API_URL = "https://api.openai.com/v1/chat/completions"   # atau endpoint apa pun
API_KEY = "..."                                           # baca dari env!
MODEL = "gpt-4o-mini"                                     # atau model apa pun

def llm(prompt: str) -> str:
    req = urllib.request.Request(API_URL, method="POST", headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }, data=json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.9,
    }).encode())
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]

def main():
    # 1. status antrean
    out = subprocess.run([str(BOT / "venv/bin/python"), str(BOT / "queue_status.py")],
                         capture_output=True, text=True, cwd=BOT).stdout
    if "NO_SESSION" in out:
        print("Refill skip: tidak ada sesi."); return
    # (parse "N live (X ID)" kalau mau ikuti aturan skip yang sama)

    # 2. pool + pick
    subprocess.run([str(BOT / "venv/bin/python"), str(BOT / "build_pool.py")], cwd=BOT)
    subprocess.run([str(BOT / "venv/bin/python"), str(BOT / "pick_drafts.py")], cwd=BOT)

    # 3. tulis komentar
    cands = json.loads((BOT / "candidates.json").read_text())
    new = []
    for c in cands:
        prompt = f"""Tulis 1 komentar Threads untuk post ini.
Bahasa: {"Indonesia casual" if c["lang"] == "id" else "English casual"}.
Isi post: {c["text"]}

Aturan:
- Kalimat 1: reaksi natural murni ke isi post (jangan sebut produk).
- Baris kosong, lalu kalimat 2: promosi halus app pemotong video panjang
  jadi shorts (arahkan ke profil, tanpa link, tanpa hard selling).
- Balas HANYA teks komentar, tanpa penjelasan."""
        comment = llm(prompt).strip()
        new.append({"url": c["url"], "author": c["author"], "lang": c["lang"],
                    "comment": comment})

    (BOT / "comments_new.json").write_text(json.dumps(new, ensure_ascii=False, indent=1))

    # 4. merge
    subprocess.run([str(BOT / "venv/bin/python"), str(BOT / "merge_comments.py")], cwd=BOT)

if __name__ == "__main__":
    main()
```

> Kode di atas contoh minimal — sesuaikan (variasi promo, cek `used_promos.txt`,
> retry, dsb.). Yang penting: outputnya `comments_new.json` dengan format
> `[{url, author, lang, comment}]`, lalu `merge_comments.py`.

---

## Jebakan portabilitas (sudah pernah kejadian)

### 1. Path hardcode

Script utama **tidak** ada path hardcode (semua pakai
`Path(__file__).resolve().parent`). Yang masih hardcode dan harus kamu
sesuaikan:

- `reply-bot/tools/fetch_refill.py` — path `BOT` (sudah diarahkan ke
  `parent.parent`, aman kalau strukturnya sama).
- Prompt refill/watchdog di `docs/` — ganti `/path/ke/reply-bot`.
- Wrapper `.sh` di `docs/` — ganti path.

### 2. Hermes-specific di watchdog

`reply-bot/threads_monitor_all.py` membaca `~/.hermes2/cron/jobs.json` untuk
cek job paused. **Kalau tidak pakai Hermes**, bagian itu otomatis di-skip
(file tidak ada → try/except lewat) — aman, tidak error.

### 3. Zona waktu

- Cron pakai TZ server. Jadwal "jam 9 WIB" di server CST = 10:00 CST.
- Script gating (muse 90-120 menit) pakai timestamp Unix — aman lintas TZ.
- Set `CRON_TZ=Asia/Jakarta` di crontab kalau mau langsung pakai jam WIB.

### 4. Dua venv terpisah

`autopost/.venv` (playwright 1.49+) dan `reply-bot/venv`
(cloakbrowser 0.5.11 + playwright 1.63.0) **berbeda versi pin** — jangan
digabung jadi satu venv. CloakBrowser versi berbeda punya API `launch()`
yang beda.

### 5. File lock

- `reply-bot/.auto_comment.lock` — daemon poster. Kalau proses mati tidak
  bersih, lock file tetap ada tapi flock otomatis lepas saat proses mati.
- `reply-bot/.scraper_cycle.lock` — scraper. Siklus yang overlap otomatis
  di-skip.

Jangan hapus lock file secara manual saat proses masih jalan.

### 6. Browser headless di VPS kecil

CloakBrowser = Chromium penuh. Satu instance ~300-500 MB RAM. Kalau VPS
1 GB, jalankan satu browser saja pada satu waktu (daemon poster saja, atau
scrape saja — jangan barengan). Scraper dan daemon memang bisa barengan
di RAM ≥2 GB.

### 7. Session cookies cepat mati

Meta suka reset session. Siapkan alur "cookies baru":

1. Export cookies dari browser (Cookie-Editor, format Netscape).
2. `python import_cookies.py cookies.txt storage_state.json .threads.com`
3. Restart daemon (lock akan lepas sendiri saat proses lama di-kill).

Buat ini sebagai SOP — jangan tunggu bot error dulu.

---

## Ringkasan "kalau pindah agent, yang perlu diurus"

1. ✅ Clone repo + install dependensi (2 venv).
2. ✅ Copy file state (checklist di atas) — terutama `replied_urls.json`.
3. ✅ Tes semua script standalone.
4. ✅ Pilih penjadwal (cron/systemd/Hermes) — template di `docs/SCHEDULING.md`.
5. ✅ Sambungkan penulis komentar (agent apa pun, prompt sudah disiapkan).
6. ✅ Sambungkan notifikasi (opsional) — kirim stdout ke mana pun.

Tidak ada langkah lain. Kalau ada masalah, cek `docs/TROUBLESHOOTING.md`.
