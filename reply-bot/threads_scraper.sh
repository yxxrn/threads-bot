#!/bin/bash
# threads_scraper.sh — cron job scraper Threads (no-agent), tiap 30 menit.
# Scrape 2 grup keyword -> found_posts_auto_*.json (bahan refill build_pool).
#
# Portable: script mencari folder reply-bot relatif ke lokasinya sendiri.
# Kalau dipakai dari luar folder (mis. ~/.hermes/scripts/), set REPLY_BOT_DIR:
#   REPLY_BOT_DIR=/path/ke/reply-bot ./threads_scraper.sh
set -euo pipefail
REPLY_BOT_DIR="${REPLY_BOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
cd "$REPLY_BOT_DIR"
exec ./venv/bin/python scraper_cycle.py
