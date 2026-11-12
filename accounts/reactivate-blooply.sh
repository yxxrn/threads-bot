#!/bin/bash
# reactivate-blooply.sh -- hidupkan lagi KEDUA job Blooply (@blooplyy_).
#   ./reactivate-blooply.sh --check          cek kesehatan kedua job, tanpa mengubah apa pun
#   ./reactivate-blooply.sh <cookies.txt>    pasang cookies segar (format Netscape) + hidupkan kedua job
#   ./reactivate-blooply.sh --login [--username NAMA]
#       login manual username + password (password dari file .env bila ada,
#       kalau tidak ditanya saat runtime; tidak pernah dicetak) + hidupkan kedua job. Bila muncul tantangan
#       verifikasi/2FA, skrip berhenti; pemilik yang menyelesaikan tantangannya.
#   ./reactivate-blooply.sh --login --request-code
#       seperti --login, tapi bila tantangan muncul, klik tombol "get a code"
#       sekali lalu berhenti (sesi TIDAK disimpan). Dipakai sekali saja atas
#       perintah pemilik; cron pengawas sesi TIDAK memakai flag ini.
#   echo 123456 | ./reactivate-blooply.sh --login --code-stdin
#       seperti --login, tapi kode verifikasi 6 digit dibaca dari stdin dan
#       dimasukkan ke form tantangan bila muncul. Kode tidak pernah dicetak.
# Aturan: sesi hanya dari akun ini sendiri (cookies atau login manual),
# JANGAN PERNAH salin state.json dari instance lain.
# verify_account.py HARUS MATCH sebelum daemon di-start; STOPPED hanya dihapus bila MATCH.
set -u
BOT=/home/ubuntu/threads-bot
PLAYWRIGHT_STATE=/home/ubuntu/threads-playwright/storage_state.json
AUTOPOST=/home/ubuntu/threads-bot-autopost
PROMO_STATE=/home/ubuntu/blooply_promo/promo_state.json
HERMES=/home/ubuntu/.local/bin/hermes

fail() { echo "GAGAL: $*" >&2; exit 1; }
note() { echo "-- $*"; }

ensure_symlink() {
  local fix="$1"
  if [ -L "$PLAYWRIGHT_STATE" ]; then
    local tgt; tgt=$(readlink "$PLAYWRIGHT_STATE")
    if [ "$tgt" = "$BOT/storage_state.json" ]; then echo "OK: symlink sesi promo sudah benar"; return 0; fi
    echo "PERINGATAN: symlink sesi promo menunjuk ke $tgt (salah)"
    [ "$fix" = 1 ] || return 1
    rm "$PLAYWRIGHT_STATE"
  elif [ -e "$PLAYWRIGHT_STATE" ]; then
    local bak="$PLAYWRIGHT_STATE.bak-$(date +%Y%m%d-%H%M)"
    echo "PERINGATAN: file sesi promo masih file lama, bukan symlink"
    [ "$fix" = 1 ] || return 1
    mv "$PLAYWRIGHT_STATE" "$bak"; echo "file lama dipindah ke $bak"
  else
    echo "PERINGATAN: file sesi promo tidak ada"
    [ "$fix" = 1 ] || return 1
  fi
  ln -s "$BOT/storage_state.json" "$PLAYWRIGHT_STATE" || fail "tidak bisa membuat symlink sesi promo"
  echo "OK: symlink sesi promo dibuat -> $BOT/storage_state.json"
}

check_promo() {
  local fix="$1"
  echo "=== job promo (post profil) ==="
  ensure_symlink "$fix" || return 1
  local out
  out=$(cd "$AUTOPOST" && .venv/bin/python -c "from api_client import ThreadsAPI; api = ThreadsAPI('$PLAYWRIGHT_STATE'); print('bootstrap ok:', bool(api.tokens.get('fb_dtsg') and api.tokens.get('lsd')))" 2>&1 | tail -3)
  echo "$out"
  echo "$out" | grep -q "bootstrap ok: True" || { echo "GAGAL: bootstrap promo gagal, sesi promo tidak hidup"; return 1; }
  echo "OK: sesi promo hidup"
  $HERMES cron list 2>/dev/null | grep -A6 "blooply-promo" | grep -E "Next run|Last run"
  if [ -f "$PROMO_STATE" ]; then python3 -c "import json; s=json.load(open('$PROMO_STATE')); print('promo_state i:', s.get('i'), '| terakhir:', s.get('done', [{}])[-1].get('key'), s.get('done', [{}])[-1].get('at'))"; fi
  return 0
}

check_daemon() {
  echo "=== daemon reply ==="
  if [ -f "$BOT/STOPPED" ]; then echo "STOPPED ada: daemon sengaja dimatikan (bukan error)"; return 1; fi
  if pgrep -f "threads-bot/poster_daemon.py" >/dev/null; then
    echo "OK: daemon jalan (pid $(pgrep -f threads-bot/poster_daemon.py | head -1))"
    tail -2 "$BOT/daemon.log" 2>/dev/null | cut -c1-140
    return 0
  fi
  echo "daemon TIDAK jalan"
  return 1
}

install_cookies() {
  local src="$1"
  [ -s "$src" ] || fail "file cookies $src kosong/tidak ada"
  local ts; ts=$(date +%Y%m%d-%H%M%S)
  for f in state.json storage_state.json; do
    [ -f "$BOT/$f" ] && cp "$BOT/$f" "$BOT/$f.bak-$ts"
  done
  "$BOT/venv/bin/python" - "$src" "$BOT/state.json" "$BOT/storage_state.json" <<'PYEOF'
import json, re, sys
src, dst1, dst2 = sys.argv[1], sys.argv[2], sys.argv[3]
cookies = []
for raw in open(src, encoding="utf-8", errors="replace"):
    line = raw.rstrip("\n")
    if not line:
        continue
    if line.startswith("#") and not line.startswith("#HttpOnly_"):
        continue
    http_only = False
    if line.startswith("#HttpOnly_"):
        line = line[len("#HttpOnly_"):]
        http_only = True
    parts = line.split("\t")
    if len(parts) < 7:
        parts = line.split()
    if len(parts) < 7:
        continue
    domain, _flag, path, secure, expires, name, value = parts[:7]
    value = re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), value)
    try:
        expires = int(expires)
    except ValueError:
        expires = -1
    cookies.append({"name": name, "value": value, "domain": domain, "path": path,
                    "expires": expires, "httpOnly": http_only,
                    "secure": secure.upper() == "TRUE", "sameSite": "Lax"})
state = {"cookies": cookies, "origins": []}
for dst in (dst1, dst2):
    with open(dst, "w") as fh:
        json.dump(state, fh)
print("cookies terpasang: %d" % len(cookies))
PYEOF
  chmod 600 "$BOT/state.json" "$BOT/storage_state.json"
  echo "OK: cookies dipasang ke state.json + storage_state.json (backup .bak-$ts)"
}

finish_revival() {
  # Langkah bersama sesudah sesi baru terpasang + terverifikasi (dipakai
  # mode cookies dan mode --login): symlink, verifikasi MATCH, hapus
  # STOPPED, start daemon bila belum jalan, cek promo.
  local label="${1:-revival}"
  ensure_symlink 1
  note "verifikasi identitas sesi..."
  local out
  out=$("$BOT/venv/bin/python" "$BOT/verify_account.py" 2>&1); echo "$out"
  echo "$out" | grep -q "^MATCH" || { echo "GAGAL: sesi tidak MATCH, daemon TIDAK di-start, STOPPED tetap." >&2; exit 1; }
  rm -f "$BOT/STOPPED"
  echo "OK: STOPPED dihapus (sesi MATCH)"
  if pgrep -f "threads-bot/poster_daemon.py" >/dev/null; then
    echo "OK: daemon sudah jalan, tidak di-start ulang"
  else
    systemd-run --user --unit=threads-poster-daemon --collect --working-directory="$BOT" "$BOT/venv/bin/python" "$BOT/poster_daemon.py" || fail "tidak bisa start daemon"
    sleep 12
    pgrep -f "threads-bot/poster_daemon.py" >/dev/null && echo "OK: daemon mulai jalan" || fail "daemon tidak jalan setelah start"
  fi
  check_promo 1 || fail "promo belum siap setelah revival"
  echo "=== SELESAI: kedua job Blooply hidup ($label) ==="
  check_daemon; check_promo 1
}

case "${1:-}" in
  --check)
    note "mode cek (tanpa perubahan)"
    check_daemon; d=$?
    check_promo 0; p=$?
    echo "=== ringkasan ==="
    [ $d -eq 0 ] && echo "daemon reply: JALAN" || echo "daemon reply: TIDAK JALAN / STOPPED"
    [ $p -eq 0 ] && echo "job promo: SIAP (sesi hidup)" || echo "job promo: BERMASALAH"
    [ $d -eq 0 ] && [ $p -eq 0 ] && exit 0 || exit 1
    ;;
  --login)
    shift
    note "mode login manual (username + password)"
    "$BOT/venv/bin/python" "$BOT/manual_login.py" "$@" || fail "login manual gagal (lihat pesan di atas); STOPPED tetap, daemon tidak di-start"
    finish_revival "login manual"
    ;;
  "")
    echo "pakai: $0 --check | $0 --login [--username NAMA] | $0 <cookies-netscape.txt>" >&2; exit 2
    ;;
  *)
    note "mode hidupkan lagi dengan cookies segar"
    install_cookies "$1"
    finish_revival "cookies"
    ;;
esac
