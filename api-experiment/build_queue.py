#!/usr/bin/env python3
"""Build posting queue for @clovebliz: muse ID chain, repo, muse EN chain, repo, ..."""
import json
from datetime import datetime, timedelta, timezone

WIB = timezone(timedelta(hours=7))

REPOS = [
 ("open-webui/open-webui","Antarmuka mirip ChatGPT buat model lokal.","UI web buat jalanin model lokal atau API, lengkap dengan chat, dokumen, dan user management."),
 ("ollama/ollama","Jalanin LLM di laptop, satu perintah.","Jalanin model seperti Llama, Qwen, atau Gemma di laptop cuma pakai satu perintah."),
 ("n8n-io/n8n","Otomasi kerjaan, nyambung ke 400+ app.","Otomasi alur kerja lewat node, nyambung ke Telegram, Sheets, sampai webhook."),
 ("Comfy-Org/ComfyUI","Bikin gambar AI pakai node, kontrol penuh.","Generator gambar berbasis node, kontrol detail sampai pipeline custom."),
 ("langgenius/dify","Bangun chatbot dan workflow AI tanpa banyak ngoding.","Bangun chatbot, RAG, dan agent lewat visual builder."),
 ("infiniflow/ragflow","Chat sama dokumen sendiri, jawabannya ada sumbernya.","Mesin RAG buat tanya jawab dokumen, lengkap dengan sitasi."),
 ("Mintplex-Labs/anything-llm","Asisten AI privat buat file dan catatan.","Asisten AI privat buat PDF dan catatan, bisa jalan lokal."),
 ("mem0ai/mem0","Memori buat agent, biar nggak lupa konteks.","Layer memori buat agent, nyimpen preferensi dan riwayat."),
 ("upstash/context7","Dokumentasi library terbaru buat coding agent.","Nyediain dokumentasi terbaru library langsung ke coding agent."),
 ("browser-use/browser-use","Agent yang bisa buka browser dan klik sendiri.","Library buat agent yang bisa buka browser, isi form, dan klik."),
 ("firecrawl/firecrawl","Ubah web jadi data bersih buat AI.","Crawl dan scrape web, hasilnya Markdown bersih buat LLM."),
 ("unclecode/crawl4ai","Crawler buat LLM, output siap pakai.","Crawler async buat AI, bisa render JS dan ekstrak struktur."),
 ("google-gemini/gemini-cli","Gemini di terminal, bisa baca repo.","Gemini di terminal, bisa baca repo dan jalanin perintah."),
 ("OpenHands/OpenHands","Agent coding yang ngerjain task di repo.","Agent coding yang bisa ngerjain issue dan buka PR."),
 ("lobehub/lobehub","Ruang kerja banyak agent, satu dashboard.","Dashboard buat ngatur banyak agent dan model."),
 ("microsoft/markitdown","PDF dan Office jadi Markdown rapi.","Konversi PDF, DOCX, dan PPTX jadi Markdown."),
 ("opendatalab/MinerU","PDF kompleks jadi teks siap masuk LLM.","Parse PDF ilmiah dan dokumen kompleks jadi teks terstruktur."),
 ("docling-project/docling","Parse dokumen, tabel, dan layout jadi data.","Parser dokumen dengan layout, tabel, dan reading order."),
 ("PaddlePaddle/PaddleOCR","OCR banyak bahasa, termasuk teks di gambar.","OCR multi bahasa, akurat buat teks di gambar dan scan."),
 ("tesseract-ocr/tesseract","OCR klasik, jalan offline di mana aja.","OCR klasik offline, tersedia di hampir semua platform."),
 ("Stirling-Tools/Stirling-PDF","Edit, gabung, dan kompres PDF di browser sendiri.","Toolkit PDF self-host: merge, split, OCR, tanda tangan."),
 ("upscayl/upscayl","Naikin resolusi gambar, jalan offline.","Upscaler gambar pakai AI, batch dan offline."),
 ("harry0703/MoneyPrinterTurbo","Video pendek dari satu topik, otomatis.","Bikin video pendek dari topik, lengkap skrip sampai subtitle."),
 ("RVC-Boss/GPT-SoVITS","Kloning suara dari satu menit audio.","Latih suara TTS dari satu menit rekaman."),
 ("remotion-dev/remotion","Bikin video pakai React, cocok buat konten rutin.","Bikin video programatik pakai React."),
 ("heygen-com/hyperframes","HTML jadi video, render otomatis.","Render video dari HTML, cocok buat otomasi konten."),
 ("nexu-io/open-design","Ruang desain AI, lokal dan kolaboratif.","Workspace desain AI lokal buat mockup dan motion."),
 ("immich-app/immich","Google Photos versi self-host.","Kelola foto dan video sendiri, mirip Google Photos."),
 ("excalidraw/excalidraw","Whiteboard buat diagram, tanpa login.","Whiteboard online buat diagram dan sketsa."),
 ("microsoft/terminal","Terminal Windows yang bisa tab dan split.","Terminal Windows dengan tab, split pane, dan profil."),
 ("Eugeny/tabby","Terminal modern, SSH dan SFTP jadi satu.","Terminal modern dengan SSH, SFTP, dan port forwarding."),
 ("alacritty/alacritty","Terminal GPU, ringan dan cepat.","Terminal GPU yang ringan dan cepat."),
 ("warpdotdev/warp","Terminal dengan agent AI bawaan.","Terminal dengan agent AI dan workflow block."),
 ("jesseduffield/lazygit","Git pakai keyboard, tanpa hafal perintah.","UI terminal buat git, stage dan commit tanpa hafal perintah."),
 ("junegunn/fzf","Cari file dan history pakai fuzzy.","Fuzzy finder buat file, history, dan branch."),
 ("BurntSushi/ripgrep","Cari teks di folder besar, cepat.","Cari teks di repo besar dengan cepat."),
 ("sharkdp/bat","Baca file di terminal pakai syntax highlight.","Pengganti cat dengan syntax highlight dan git diff."),
 ("hoppscotch/hoppscotch","Tes API di browser, mirip Postman.","Klien API di browser, support REST dan GraphQL."),
 ("termux/termux-app","Linux di Android, buat script darurat.","Terminal Linux di Android dengan package manager."),
 ("dani-garcia/vaultwarden","Server password sendiri, ringan.","Server password kompatibel Bitwarden, ringan."),
 ("louislam/uptime-kuma","Monitor website dan dapat notif.","Monitoring uptime dengan notifikasi Telegram."),
 ("coollabsio/coolify","Deploy app sendiri, mirip Vercel.","PaaS self-host buat deploy app dan database."),
 ("makeplane/plane","Manajemen proyek open source.","Manajemen proyek open source, alternatif Jira."),
 ("localsend/localsend","Kirim file antar device tanpa internet.","Kirim file antar device satu WiFi, tanpa internet."),
 ("microsoft/PowerToys","Utility Windows: resize, rename, color picker.","Kumpulan utility Windows: PowerRename, FancyZones, Color Picker."),
 ("yt-dlp/yt-dlp","Download video dari banyak situs.","Downloader video dari YouTube dan ratusan situs."),
 ("tw93/Pake","Website jadi app desktop ringan.","Bungkus website jadi app desktop ringan."),
 ("marktext/marktext","Editor markdown yang bersih.","Editor Markdown fokus, live preview."),
 ("toeverything/AFFiNE","Catatan, kanvas, dan tugas jadi satu.","Gabungan Notion dan Miro: dokumen, kanvas, tugas."),
 ("usememos/memos","Catatan cepat buat diri sendiri.","Catatan cepat self-host, mirip Twitter pribadi."),
]

MUSE_ID = [
 ("Masih nunggu waiting list muse.ai? Bisa di-skip kok.\n\n1. Download Pawxy di Play Store\n2. Buka Pawxy, connect VPN-nya, pilih region US\n3. Siapkan akun IG buat konfirmasi umur. Kalau nggak punya IG, bisa pakai kartu debit (Jago, blu, apa aja)\n4. Masuk muse.ai, masukin kode KGG3P8, token 1 miliar langsung masuk\n\nSisanya di bawah.",
  "5. Selain token, kalian juga dapat VPS gratis. Speknya 2 vCPU AMD EPYC 9D25, RAM 7,7 GB\n6. Tokennya nggak pernah kedaluwarsa. Selama akun aktif, VPS ikut hidup, tanpa biaya bulanan\n7. Bonus 3 miliar token lewat bot Telegram Satu Digital: https://t.me/satudigitalbot?start=ref_1323141169\n\nKodenya KGG3P8, isi waktu daftar biar token langsung masuk."),
 ("Antrean muse.ai masih panjang? Ada jalan pintas, sekitar 5 menit.\n\n1. Download Pawxy di Play Store\n2. Connect VPN bawaan Pawxy, pilih region US\n3. Siapkan akun IG buat verifikasi umur, kartu debit juga bisa\n4. Daftar muse.ai pakai email, isi kode KGG3P8, token 1 miliar langsung masuk\n\nLangkah sisanya di bawah.",
  "5. Bonusnya VPS gratis: 2 vCPU AMD EPYC 9D25, RAM 7,7 GB\n6. Token dan VPS nggak ada masa aktifnya selama akun hidup\n7. Tambahan 3 miliar token dari bot Telegram Satu Digital: https://t.me/satudigitalbot?start=ref_1323141169\n\nKodenya KGG3P8, masukin pas daftar."),
 ("VPS gratis 2 vCPU dan token muse, masih ada slot.\n\n1. Download Pawxy di Play Store\n2. Buka app-nya, connect VPN, pilih US\n3. Siapkan akun IG buat konfirmasi umur\n4. Masuk muse.ai, masukin kode KGG3P8, token 1 miliar masuk\n\nCara lengkapnya di bawah.",
  "5. Bonus VPS gratis: 2 vCPU AMD EPYC 9D25, RAM 7,7 GB\n6. Token 1 miliar dan VPS berlaku selama akun aktif, tanpa biaya bulanan\n7. Bonus 3 miliar token lewat Telegram Satu Digital: https://t.me/satudigitalbot?start=ref_1323141169\n\nKodenya KGG3P8, isi waktu daftar."),
]

MUSE_EN = [
 ("Still waiting on the muse.ai waiting list? You can skip it.\n\n1. Download Pawxy from the Play Store\n2. Open Pawxy, connect its VPN, pick the US region\n3. Have an IG account ready for age verification. No IG? A debit card works (Jago, blu, any card)\n4. Log in to muse.ai, enter KGG3P8, and 1 billion tokens land in your account\n\nMore below.",
  "5. You also get a free VPS included with muse. Specs: 2 vCPU AMD EPYC 9D25, 7.7 GB RAM\n6. The free tokens never expire. As long as your account stays active, the VPS stays up too, with no monthly fees\n7. Bonus: 3 billion extra tokens via the Satu Digital Telegram bot: https://t.me/satudigitalbot?start=ref_1323141169\n\nThe code's KGG3P8, enter it when you sign up so the tokens go straight to your account."),
 ("The muse.ai queue is long. There's a shortcut that takes about 5 minutes.\n\n1. Download Pawxy from the Play Store\n2. Connect the VPN built into Pawxy, pick the US region\n3. Have an IG account ready for age check, a debit card works too\n4. Sign up for muse.ai with email, enter KGG3P8, 1 billion tokens land\n\nSteps continue below.",
  "5. You get a free VPS: 2 vCPU AMD EPYC 9D25, 7.7 GB RAM\n6. Tokens and VPS never expire while the account is alive\n7. Extra 3 billion tokens via the Satu Digital Telegram bot: https://t.me/satudigitalbot?start=ref_1323141169\n\nCode is KGG3P8, enter it at signup."),
 ("Free 2 vCPU VPS plus muse tokens, slots still open.\n\n1. Download Pawxy from the Play Store\n2. Open it, connect the VPN, pick US\n3. Have an IG account ready for age verification\n4. Go to muse.ai, enter KGG3P8, 1 billion tokens land\n\nFull steps below.",
  "5. You get a 2 vCPU AMD EPYC 9D25 VPS with 7.7 GB RAM, free\n6. Tokens and VPS stay valid while the account is active, no monthly fee\n7. Bonus 3 billion tokens via the Satu Digital Telegram bot: https://t.me/satudigitalbot?start=ref_1323141169\n\nCode is KGG3P8, enter it at signup."),
]


import json as _json
_GROUPS={x['repo']:x['group'] for x in _json.load(open('repos50.json'))}
_BENEFIT={
 "AI & Agen":["Cocok buat yang mau coba AI tanpa langganan bulanan.","Enak buat eksperimen workflow AI di mesin sendiri.","Buat yang males bayar API tapi tetap pengin coba model."],
 "Dokumen & OCR":["Cocok buat yang sering ngurusi PDF dan dokumen kantor.","Ngebantu kalau kerjaanmu penuh scan dan laporan.","Buat yang males copy paste manual dari PDF."],
 "Media & Kreator":["Cocok buat creator yang ngerjain semuanya sendiri.","Ngebantu kerjaan konten yang biasanya makan waktu.","Buat editor atau clipper yang butuh cepat."],
 "Developer & Terminal":["Cocok buat yang hidup di terminal.","Ngebantu kerjaan harian developer.","Buat yang suka tool ringan tanpa GUI berat."],
 "Self-host & Utility":["Cocok buat yang punya VPS nganggur.","Buat yang pelan-pelan pindah dari SaaS.","Enak buat homelab kecil-kecilan."],
}

MUSE_P1_MEDIA = ["/home/agentuser/clove/media/muse-latest-2.jpg",
                 "/home/agentuser/clove/media/muse-latest-3.jpg",
                 "/home/agentuser/clove/media/muse-latest-4.jpg"]
MUSE_P2_MEDIA = ["/home/agentuser/clove/media/muse-settings.jpg",
                 "/home/agentuser/clove/media/muse-specs.jpg"]

def slug(repo): return repo.replace("/", "-")

blocks = []
for i, (repo, hook, desc) in enumerate(REPOS):
    if i % 2 == 0:
        t = MUSE_ID[(i//2) % 3]
        blocks.append({"kind":"muse_id","label":f"muse-id-{(i//2)%3+1}","parts":[
            {"text":t[0],"media":MUSE_P1_MEDIA},
            {"text":t[1],"media":MUSE_P2_MEDIA}]})
    else:
        t = MUSE_EN[(i//2) % 3]
        blocks.append({"kind":"muse_en","label":f"muse-en-{(i//2)%3+1}","parts":[
            {"text":t[0],"media":MUSE_P1_MEDIA},
            {"text":t[1],"media":MUSE_P2_MEDIA}]})
    grp=_GROUPS.get(repo,"AI & Agen")
    benefit=_BENEFIT[grp][i%3]
    text = f"{hook}\n\n{desc} {benefit}\n\ngithub.com/{repo}"
    blocks.append({"kind":"repo","label":repo,"parts":[
        {"text":text,"media":[f"/home/agentuser/clove/repo50/{repo.replace('/','-')}.png"]}]})

INTERVAL = timedelta(hours=3, minutes=30)
due = datetime(2026, 10, 21, 8, 0, tzinfo=WIB)
now_cut = datetime(2026, 10, 21, 7, 25, tzinfo=WIB)
for b in blocks:
    while due <= now_cut:
        due += INTERVAL
    b["due_at"] = due.isoformat()
    b["status"] = "pending"
    due += INTERVAL

for i,b in enumerate(blocks,1): b["id"]=i
json.dump(blocks, open("clove_queue.json","w"), ensure_ascii=False, indent=1)
print("blocks", len(blocks), "repo", sum(1 for b in blocks if b['kind']=='repo'),
      "muse", sum(1 for b in blocks if b['kind'].startswith('muse')))
print("first", blocks[0]["due_at"], blocks[0]["label"])
print("last", blocks[-1]["due_at"], blocks[-1]["label"])
