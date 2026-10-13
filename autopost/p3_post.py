#!/usr/bin/env python3
"""Generic warm-up post @clovebliz: --file TEKS [--media GAMBAR] (single post).

Dipakai one-shot repo (`p3-repo2`); post muse chain pakai `post.py -f` langsung.
"""
import argparse
from pathlib import Path

import post

HERE = Path(__file__).resolve().parent
post.STATE = HERE / "storage_state_p3.json"
post.PROFILE_URL = "https://www.threads.com/@clovebliz"

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="file teks (single post)")
    ap.add_argument("--media", default=None, help="opsional: 1 gambar")
    args = ap.parse_args()

    fp = Path(args.file)
    fp = fp if fp.is_absolute() else HERE / fp
    text = fp.read_text(encoding="utf-8").strip()
    media = None
    if args.media:
        mp = Path(args.media)
        mp = mp if mp.is_absolute() else HERE / mp
        media = [[mp]]
    post.post_parts([text], media=media)
