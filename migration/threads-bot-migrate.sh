#!/bin/bash
# threads-bot-migrate.sh — pasang / pulihkan Threads bot di sebuah mesin.
#
# Dua mode:
#   1) INSTALL (tanpa --state)  : mesin kosong -> kode + venv + deps + provider
#                                 + script cron + 5 job Hermes terdaftar.
#   2) RESTORE (dengan --state): install + timpa seluruh state runtime dari
#                                 bundle hasil threads-bot-export-state.sh.
#
# Jalankan DI MESIN SUMBER (yang punya akses SSH ke target):
#   ./threads-bot-migrate.sh <target-ip>                      # install bersih
#   ./threads-bot-migrate.sh <target-ip> --state /tmp/s.tar.gz # restore penuh
#
# Opsi:
#   --user ubuntu        user SSH + pemilik instalasi (default: ubuntu)
#   --no-cron            jangan daftarkan job Hermes
#   --resume-all         job blooply/clove dibuat aktif (default: paused)
#
# Idempoten: aman dijalankan ulang. Tidak menyentuh ~/.hermes/config.yaml
# punya orang lain — hanya menambah/mengganti provider 9router-go.
set -euo pipefail

TARGET="${1:-}"; shift || true
[ -n "$TARGET" ] || { echo "usage: $0 <target-ip> [--state FILE] [--user U] [--no-cron] [--resume-all]"; exit 1; }

SSTATE=""; RUN_USER="ubuntu"; DO_CRON=1; RESUME_ALL=0
while [ $# -gt 0 ]; do
  case "$1" in
    --state) SSTATE="$2"; shift 2 ;;
    --user) RUN_USER="$2"; shift 2 ;;
    --no-cron) DO_CRON=0; shift ;;
    --resume-all) RESUME_ALL=1; shift ;;
    *) echo "opsi tidak dikenal: $1"; exit 1 ;;
  esac
done

HERE="$(cd "$(dirname "$0")" && pwd)"
SSH=(ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$RUN_USER@$TARGET")
SUDO=(sudo -n -u agentuser bash -s)
REPO="${THREADS_BOT_REPO:-https://github.com/yxxrn/threads-bot.git}"
BOT=/home/agentuser/threads-bot

say () { printf '\n\033[1m== %s\033[0m\n' "$*"; }

say "1/8 prasyarat di $TARGET"
"${SSH[@]}" 'sudo -n true && echo "sudo: ok"; python3 -V; git --version | head -1; command -v rsync >/dev/null && echo "rsync: ok" || echo "rsync: TIDAK ADA (akan pakai tar)"'

say "2/8 kode + layout"
"${SSH[@]}" "${SUDO[@]}" <<'EOS'
set -e
export HOME=/home/agentuser
REPO="${THREADS_BOT_REPO:-https://github.com/yxxrn/threads-bot.git}"
rm -rf /tmp/tb-src && git clone --depth 1 -q "$REPO" /tmp/tb-src
mkdir -p "$HOME/threads-bot" "$HOME/threads-bot-repo" "$HOME/clove/media" \
         "$HOME/clove/repo50" "$HOME/blooply_promo/chain1" "$HOME/blooply_promo/chain2" \
         "$HOME/threads-playwright" "$HOME/.hermes/scripts"
# salin kode tanpa menimpa state yang sudah ada (restore terjadi di langkah 6)
for d in reply-bot api-experiment autopost docs; do
  src=/tmp/tb-src/$d; [ -d "$src" ] || continue
  case "$d" in
    reply-bot)      dst="$HOME/threads-bot" ;;
    api-experiment) dst="$HOME/threads-bot-repo/api-experiment" ;;
    autopost)       dst="$HOME/autopost" ;;
    docs)           dst="$HOME/threads-bot-docs" ;;
  esac
  mkdir -p "$dst"; cp -an "$src/." "$dst/" 2>/dev/null || true
done
echo "kode: $(ls "$HOME/threads-bot" | wc -l) file di $HOME/threads-bot"
EOS

say "3/8 venv reply-bot (playwright + cloakbrowser)"
"${SSH[@]}" "${SUDO[@]}" <<'EOS'
set -e
export HOME=/home/agentuser
cd "$HOME/threads-bot"
[ -x venv/bin/python ] || python3 -m venv venv
./venv/bin/python -m pip install -q --upgrade pip 2>&1 | tail -1
./venv/bin/python -m pip install -q -r requirements.txt 2>&1 | tail -5
./venv/bin/python - <<'PY'
from playwright.sync_api import sync_playwright
import os
with sync_playwright() as p:
    exe = p.chromium.executable_path
print("chromium:", exe, "ada:", os.path.exists(exe))
PY
EOS

say "4/8 venv API path (curl_cffi + Pillow)"
"${SSH[@]}" "${SUDO[@]}" <<'EOS'
set -e
export HOME=/home/agentuser
cd "$HOME/threads-playwright"
[ -x .venv/bin/python ] || python3 -m venv .venv
./.venv/bin/python -m pip install -q --upgrade pip 2>&1 | tail -1
./.venv/bin/python -m pip install -q "curl_cffi>=0.7" Pillow 2>&1 | tail -5
./.venv/bin/python -c "import curl_cffi,PIL,sys;sys.path.insert(0,'/home/agentuser/threads-bot-repo/api-experiment');from api_client import ThreadsAPI;print('api_client OK', curl_cffi.__version__)"
EOS

say "5/8 provider 9router-go + entri agnes"
# key diambil dari mesin sumber (config.yaml lokal), dikirim lewat stdin
python3 - "$HERE" <<'PY' > /tmp/_9r_key.txt
import sys, yaml, os
sys.path.insert(0, sys.argv[1])
p = os.path.expanduser("~/.hermes/config.yaml")
c = yaml.safe_load(open(p)) or {}
for x in (c.get("custom_providers") or []):
    if x.get("name") == "9router-go":
        print(x["api_key"]); break
else:
    sys.exit("9router-go tidak ada di config sumber")
PY
"${SSH[@]}" "${SUDO[@]}" <<EOS
set -e
export HOME=/home/agentuser
KEY="\$(cat)"
CFG="\$HOME/.hermes/config.yaml"
[ -f "\$CFG" ] || { echo "config.yaml tidak ada di \$CFG"; exit 1; }
cp -a "\$CFG" "\$CFG.bak-migrate-\$(date +%Y%m%d-%H%M%S)"
python3 - "\$KEY" <<'PY'
import sys, yaml
key = sys.argv[1]
cfg = yaml.safe_load(open("/home/agentuser/.hermes/config.yaml")) or {}
provider = {
    "name": "9router-go",
    "base_url": "http://100.86.193.19:20128/v1",
    "api_key": key,
    "model": "agnes/agnes-2.5-flash",
    "models": {
        "agnes/agnes-2.5-flash": {"context_length": 512000},
        "agnes/agnes-3.0-flash": {"context_length": 512000},
        "oc/mimo-v2.6-flash-free": {"context_length": 131072},
        "cl/poolside/laguna-s-2.1:free": {},
    },
}
cps = [p for p in (cfg.get("custom_providers") or []) if p.get("name") != "9router-go"]
cps.append(provider)
cfg["custom_providers"] = cps
with open("/home/agentuser/.hermes/config.yaml", "w") as f:
    yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)
print("provider 9router-go ditulis, models:", list(provider["models"]))
PY
chmod 600 "\$CFG"
EOS
< /tmp/_9r_key.txt
rm -f /tmp/_9r_key.txt

say "6/8 state runtime"
if [ -n "$SSTATE" ]; then
  [ -f "$SSTATE" ] || { echo "bundle tidak ditemukan: $SSTATE"; exit 1; }
  echo "kirim bundle $(du -h "$SSTATE" | cut -f1) ke $TARGET"
  if command -v rsync >/dev/null; then
    rsync -az -e "ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no" "$SSTATE" "$RUN_USER@$TARGET:/tmp/tb-state.tar.gz"
  else
    scp -q -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$SSTATE" "$RUN_USER@$TARGET:/tmp/tb-state.tar.gz"
  fi
  "${SSH[@]}" "${SUDO[@]}" <<'EOS'
set -e
export HOME=/home/agentuser
ST=$(mktemp -d); trap 'rm -rf "$ST"' EXIT
tar -xzf /tmp/tb-state.tar.gz -C "$ST"
echo "--- isi bundle ---"; sed -n '1,12p' "$ST/MANIFEST.txt"
# state reply-bot (jangan timpa kode)
for f in session.json state.json comments.json comments_new.json retry_queue.json \
         replied_urls.json posted_history.jsonl auto_log.json pool_ready.json \
         candidates.json skip_urls.txt used_promos.txt scraper_state.json \
         daemon.log cron.log scraper.log refill_check.json; do
  [ -e "$ST/threads-bot/$f" ] && cp -a "$ST/threads-bot/$f" "$HOME/threads-bot/$f"
done
cp -an "$ST/threads-bot/"found_posts*.json "$HOME/threads-bot/" 2>/dev/null || true
cp -an "$ST/threads-bot/"post_texts*.json  "$HOME/threads-bot/" 2>/dev/null || true
[ -d "$ST/threads-bot/shots" ] && cp -an "$ST/threads-bot/shots" "$HOME/threads-bot/" 2>/dev/null || true
# storage_state / cookies
cp -an "$ST/threads-playwright/"storage_state*.json "$HOME/threads-playwright/" 2>/dev/null || true
[ -f "$ST/threads-playwright/post.py" ] && cp -an "$ST/threads-playwright/post.py" "$HOME/threads-playwright/" 2>/dev/null || true
# clove
for f in clove_queue.json queue_state.json runner.log posted.log clove_schedule.csv; do
  [ -e "$ST/clove/$f" ] && cp -a "$ST/clove/$f" "$HOME/clove/$f"
done
for d in media repo50; do [ -d "$ST/clove/$d" ] && cp -an "$ST/clove/$d/." "$HOME/clove/$d/" 2>/dev/null || true; done
# blooply promo
for f in variants.json media_manifest.json promo_state.json promo.log; do
  [ -e "$ST/blooply_promo/$f" ] && cp -a "$ST/blooply_promo/$f" "$HOME/blooply_promo/$f"
done
for d in chain1 chain2; do [ -d "$ST/blooply_promo/$d" ] && cp -an "$ST/blooply_promo/$d/." "$HOME/blooply_promo/$d/" 2>/dev/null || true; done
# autopost counters
for f in .promo_state.json .x_muse_state.json .p2_muse_state.json .fb_promo_state.json; do
  [ -e "$ST/autopost/$f" ] && cp -a "$ST/autopost/$f" "$HOME/autopost/$f"
done
[ -d "$ST/autopost/media" ] && cp -an "$ST/autopost/media/." "$HOME/autopost/media/" 2>/dev/null || true
for f in storage_state.json storage_state_p3.json storage_state_x.json storage_state_fb.json; do
  [ -e "$ST/autopost/$f" ] && cp -a "$ST/autopost/$f" "$HOME/autopost/$f"
done
chmod 600 "$HOME/threads-bot/state.json" "$HOME/threads-bot/session.json" 2>/dev/null || true
chmod 600 "$HOME/threads-playwright/"storage_state*.json 2>/dev/null || true
echo "state dipulihkan"
EOS
else
  echo "mode INSTALL: state tidak dipulihkan (kirim cookies baru setelah ini)"
fi

say "7/8 script cron + 5 job Hermes"
"${SSH[@]}" "${SUDO[@]}" <<'EOS'
set -e
export HOME=/home/agentuser
S="$HOME/.hermes/scripts"; mkdir -p "$S"

# --- wrapper scraper: portabel, override lewat REPLY_BOT_DIR ---
cat > "$S/threads_scraper.sh" <<'SH'
#!/bin/bash
set -euo pipefail
BOT="${REPLY_BOT_DIR:-/home/agentuser/threads-bot}"
cd "$BOT"
exec ./venv/bin/python scraper_cycle.py --groups 4 --max-age-hours "${SCRAPER_MAX_AGE:-168}"
SH

# --- wrapper monitor (watchdog) ---
cat > "$S/threads_monitor_all.sh" <<'SH'
#!/bin/bash
set -euo pipefail
export THREADS_BOT_DIR="${THREADS_BOT_DIR:-/home/agentuser/threads-bot}"
export HERMES_CRON_DIR="${HERMES_CRON_DIR:-/home/agentuser/.hermes/cron}"
export REFILL_JOB_ID="${REFILL_JOB_ID:-__REFILL_ID__}"
cd "$THREADS_BOT_DIR"
exec "$THREADS_BOT_DIR/venv/bin/python" "$THREADS_BOT_DIR/threads_monitor_all.py"
SH

cat > "$S/blooply-promo.sh" <<'SH'
#!/bin/bash
set -euo pipefail
cd /home/agentuser/threads-playwright
exec ./.venv/bin/python /home/agentuser/blooply_promo/blooply_promo_api.py
SH

cat > "$S/clove-post.sh" <<'SH'
#!/bin/bash
set -euo pipefail
cd /home/agentuser/threads-playwright
exec ./.venv/bin/python /home/agentuser/clove_runner_api.py
SH

chmod +x "$S"/*.sh

# prompt agent: pakai yang ada di repo (sudah portabel), ganti path kalau beda
BOT="$HOME/threads-bot"
sed "s#/path/ke/reply-bot#$BOT#g" "$BOT/refill_prompt.txt"   > "$S/refill_prompt.txt"
sed "s#/path/ke/reply-bot#$BOT#g" "$BOT/watchdog_prompt.txt" > "$S/watchdog_prompt.txt"
echo "script terpasang: $(ls "$S" | tr '\n' ' ')"
EOS

if [ "$DO_CRON" = "1" ]; then
  "${SSH[@]}" "${SUDO[@]}" <<'EOS'
set -e
export HOME=/home/agentuser
H="$HOME/.hermes/hermes-agent/venv/bin/hermes"
S="$HOME/.hermes/scripts"
CHAT="${TELEGRAM_CHAT_ID:-1323141169}"
PAUSED_FLAG="${RESUME_ALL:+}"

exists () { "$H" cron list 2>/dev/null | grep -q "Name: *$1\$"; }

if exists threads-scraper; then echo "skip: threads-scraper sudah ada"; else
  "$H" cron create "every 30m" --name threads-scraper --no-agent \
    --script threads_scraper.sh --deliver local >/dev/null && echo "ok: threads-scraper"
fi

if exists threads-auto-cycle; then echo "skip: threads-auto-cycle sudah ada"; else
  "$H" cron create "every 15m" "$(cat "$S/refill_prompt.txt")" --name threads-auto-cycle \
    --deliver "telegram:$CHAT" --model agnes/agnes-2.5-flash --provider 9router-go \
    --workdir "$HOME/threads-bot" >/dev/null && echo "ok: threads-auto-cycle"
fi

# id job refill dibutuhkan monitor (cek paused) -> suntik setelah dibuat
RID=$("$H" cron list 2>/dev/null | awk '/Name: *threads-auto-cycle/{print prev} {prev=$1}' | tr -d ' ')
if [ -n "$RID" ]; then sed -i "s/__REFILL_ID__/$RID/" "$S/threads_monitor_all.sh"; fi

if exists threads-watchdog; then echo "skip: threads-watchdog sudah ada"; else
  "$H" cron create "every 30m" "$(cat "$S/watchdog_prompt.txt")" --name threads-watchdog \
    --monitor-script threads_monitor_all.sh --deliver "telegram:$CHAT" \
    --model agnes/agnes-2.5-flash --provider 9router-go \
    --workdir "$HOME/threads-bot" >/dev/null && echo "ok: threads-watchdog"
fi

# blooply/clove: butuh variants.json / clove_queue.json. Kalau belum ada, paused.
for pair in "blooply-promo:every 240m:blooply-promo.sh:/home/agentuser/blooply_promo/variants.json" \
            "clove-post:every 15m:clove-post.sh:/home/agentuser/clove/clove_queue.json"; do
  IFS=: read -r name sched script need <<<"$pair"
  exists "$name" && { echo "skip: $name sudah ada"; continue; }
  if [ -e "$need" ]; then
    "$H" cron create "$sched" --name "$name" --no-agent --script "$script" \
      --deliver "telegram:$CHAT" >/dev/null && echo "ok: $name (aktif)"
  else
    "$H" cron create "$sched" --name "$name" --no-agent --script "$script" \
      --deliver "telegram:$CHAT" --paused --paused-reason "menunggu $need" >/dev/null \
      && echo "ok: $name (paused, menunggu $(basename "$need"))"
  fi
done

echo "--- daftar job ---"
"$H" cron list 2>&1 | grep -E "^\s+[0-9a-f]{12}|Name:|Schedule:|Next run:"
EOS
fi

say "8/8 verifikasi"
"${SSH[@]}" "${SUDO[@]}" <<'EOS'
export HOME=/home/agentuser
B="$HOME/threads-bot"
echo "--- kode ---"; ls "$B" | wc -l
echo "--- venv ---"; "$B/venv/bin/python" -V
echo "--- provider ---"
python3 - <<'PY'
import yaml
c=yaml.safe_load(open("/home/agentuser/.hermes/config.yaml"))
p=[x for x in c.get("custom_providers") or [] if x.get("name")=="9router-go"]
print("9router-go:", "ada" if p else "TIDAK ADA", list(p[0]["models"]) if p else "")
PY
echo "--- state ---"
"$B/venv/bin/python" "$B/queue_status.py" 2>/dev/null || echo "queue_status: belum ada antrean (normal untuk instalasi baru)"
for f in session.json state.json retry_queue.json replied_urls.json comments.json; do
  [ -e "$B/$f" ] && echo "  ada  $f" || echo "  KOSONG $f"
done
echo "--- monitor ---"; "$HOME/.hermes/scripts/threads_monitor_all.sh" || true
EOS

say "SELESAI"
cat <<'TXT'
Langkah manual yang tersisa:
  1. Kirim cookies Threads baru -> login.py / import_cookies.py, lalu:
       ./venv/bin/python check_login.py
  2. Mulai sesi: tulis session.json (started_at + duration_hours: null)
  3. Nyalakan daemon poster (systemd user unit, bukan nohup)
  4. Kalau variants.json / clove_queue.json sudah ada: hermes cron resume <id>
TXT