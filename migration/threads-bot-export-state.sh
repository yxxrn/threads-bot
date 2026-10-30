#!/bin/bash
# threads-bot-export-state.sh — jalankan DI MESIN SUMBER (yang botnya masih hidup).
#
# Membuat satu bundle tar.gz berisi SELURUH state runtime yang di-gitignore:
# antrean, tombstone, replied_urls, session/cookies, counter promo, media,
# dan jobs.json Hermes. Bundle inilah yang dipulihkan di mesin tujuan.
#
# Pakai:
#   ./threads-bot-export-state.sh                 # -> /tmp/threads-bot-state-<ts>.tar.gz
#   OUT=/path/file.tar.gz ./threads-bot-export-state.sh
#
# Aman dijalankan saat bot hidup: file dibaca apa adanya (copy), tidak mengubah
# state. Lock tidak diikutkan supaya mesin tujuan tidak mengira ada proses lain.
set -euo pipefail

HOME_DIR="${HOME:-/home/agentuser}"
BOT="${THREADS_BOT_DIR:-$HOME_DIR/threads-bot}"
PLAY="${THREADS_PLAYWRIGHT_DIR:-$HOME_DIR/threads-playwright}"
CLOVE="${CLOVE_DIR:-$HOME_DIR/clove}"
PROMO="${BLOOPLY_PROMO_DIR:-$HOME_DIR/blooply_promo}"
AUTO="${AUTOPOST_DIR:-$HOME_DIR/autopost}"
CRON="${HERMES_CRON_DIR:-$HOME_DIR/.hermes/cron}"
TS="$(date +%Y%m%d-%H%M%S)"
OUT="${OUT:-/tmp/threads-bot-state-$TS.tar.gz}"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

mkdir -p "$STAGE"

copy_if () {  # copy_if <src> <dst-rel>
  [ -e "$1" ] || return 0
  mkdir -p "$STAGE/$(dirname "$2")"
  cp -a "$1" "$STAGE/$2"
}

echo "== mengumpulkan state =="

# --- reply bot: antrean + histori (PALING PENTING) ---
for f in session.json state.json comments.json comments_new.json retry_queue.json \
         replied_urls.json posted_history.jsonl auto_log.json pool_ready.json \
         candidates.json skip_urls.txt used_promos.txt scraper_state.json \
         daemon.log cron.log scraper.log refill_check.json session*.json; do
  copy_if "$BOT/$f" "threads-bot/$f"
done
# found_posts / post_texts: bahan build_pool (boleh besar, tetap diikutkan)
for f in "$BOT"/found_posts*.json "$BOT"/post_texts*.json; do
  [ -e "$f" ] && copy_if "$f" "threads-bot/$(basename "$f")"
done
copy_if "$BOT/shots" "threads-bot/shots"
copy_if "$BOT/tools" "threads-bot/tools"

# --- storage_state (cookies browser) ---
for f in "$PLAY"/storage_state*.json; do
  [ -e "$f" ] && copy_if "$f" "threads-playwright/$(basename "$f")"
done
copy_if "$PLAY/post.py" "threads-playwright/post.py"

# --- clove: antrean + progres + media ---
for f in clove_queue.json queue_state.json runner.log posted.log clove_schedule.csv; do
  copy_if "$CLOVE/$f" "clove/$f"
done
copy_if "$CLOVE/media" "clove/media"
copy_if "$CLOVE/repo50" "clove/repo50"

# --- blooply promo: rotasi varian + manifest + media chain ---
for f in variants.json media_manifest.json promo_state.json promo.log; do
  copy_if "$PROMO/$f" "blooply_promo/$f"
done
copy_if "$PROMO/chain1" "blooply_promo/chain1"
copy_if "$PROMO/chain2" "blooply_promo/chain2"

# --- autopost: counter gating + media ---
for f in storage_state.json storage_state_p3.json storage_state_x.json storage_state_fb.json \
         .promo_state.json .x_muse_state.json .p2_muse_state.json .fb_promo_state.json; do
  copy_if "$AUTO/$f" "autopost/$f"
done
copy_if "$AUTO/media" "autopost/media"

# --- Hermes: definisi job + notepad (bukan DB eksekusi) ---
copy_if "$CRON/jobs.json" "hermes/cron/jobs.json"
copy_if "$CRON/notepad.db" "hermes/cron/notepad.db"

# --- manifest: apa saja yang ikut + ukuran + host asal ---
{
  echo "exported_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "source_host=$(hostname)"
  echo "source_bot_dir=$BOT"
  echo "git_commit=$(git -C "$BOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
  echo "--- files ---"
  ( cd "$STAGE" && find . -type f -printf '%10s  %p\n' | sort -k2 )
} > "$STAGE/MANIFEST.txt"

tar -czf "$OUT" -C "$STAGE" .
chmod 600 "$OUT"

echo "== selesai =="
echo "bundle : $OUT"
echo "ukuran : $(du -h "$OUT" | cut -f1)"
echo "isi    : $(find "$STAGE" -type f | wc -l) file"
echo
echo "Langkah berikut (dari mesin mana pun di tailnet):"
echo "  scp $OUT ubuntu@<target>:/tmp/"
echo "  ./threads-bot-migrate.sh <target-ip> --state /tmp/$(basename "$OUT")"