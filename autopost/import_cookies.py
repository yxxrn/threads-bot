#!/usr/bin/env python3
"""Convert Netscape cookie file (Cookie-Editor) → Playwright storage_state.json.

Usage:
  import_cookies.py [src_netscape] [dst_state] [extra_domains_csv]

Defaults keep the old Threads behavior: cookies.txt → storage_state.json
mapped to .threads.com/.threads.net. X: import_cookies.py x_cookies.txt storage_state_x.json .x.com,.twitter.com
"""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parent
NETSCAPE = ROOT / "cookies.txt"
STATE = ROOT / "storage_state.json"

SAMESITE_MAP = {
    "Lax": "Lax",
    "Strict": "Strict",
    "None": "None",
    "no_restriction": "None",
}

def domain_flags(domain: str):
    # Netscape: domain starts with "." → includeSubdomains TRUE
    if domain.startswith("."):
        return domain, True
    return domain, False

def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else NETSCAPE
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else STATE
    if len(sys.argv) > 3 and sys.argv[3].strip():
        extra_domains = {d.strip() for d in sys.argv[3].split(",") if d.strip()}
    else:
        extra_domains = {".threads.com", ".threads.net"}
    cookies = []
    seen = set()
    for line in src.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") and not line.startswith("#HttpOnly_"):
            continue
        http_only = False
        if line.startswith("#HttpOnly_"):
            http_only = True
            line = line[len("#HttpOnly_"):]
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        domain, include_sub, path, secure, expires, name, value = parts[:7]
        # strip quotes
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        # unescape \054 → ,
        value = value.replace("\\054", ",")
        domain, _ = domain_flags(domain)
        try:
            exp = int(expires)
        except ValueError:
            exp = 0

        # emit for original + extra domains (dedup)
        for d in {domain} | extra_domains:
            key = (d, path, name)
            if key in seen:
                continue
            seen.add(key)
            cookies.append({
                "name": name,
                "value": value,
                "domain": d,
                "path": path or "/",
                "expires": float(exp),
                "httpOnly": http_only,
                "secure": secure.upper() == "TRUE",
                "sameSite": "None",
            })

    state = {"cookies": cookies, "origins": []}
    dst.write_text(json.dumps(state, indent=2))
    dst.chmod(0o600)
    print(f"wrote {len(cookies)} cookies → {dst}")

if __name__ == "__main__":
    main()
