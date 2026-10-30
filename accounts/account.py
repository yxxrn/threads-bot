#!/usr/bin/env python3
"""Satu CLI kecil buat semua akun Threads.

Registry: accounts/registry.json (relatif ke file ini).
Semua path pakai ~ supaya pindah mesin cuma perlu edit registry.

Contoh:
  ./account.py list
  ./account.py status clove
  ./account.py check clove
  ./account.py post-next clove
  ./account.py pause clove
  ./account.py resume blooply
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REG = HERE / "registry.json"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def expand(p: str | None) -> str | None:
    if not p:
        return None
    return os.path.expanduser(os.path.expandvars(p))


def load_reg() -> dict:
    return json.loads(REG.read_text())


def hermes_bin(reg: dict) -> str:
    return expand(reg.get("_meta", {}).get("hermes_bin") or "~/.hermes/hermes-agent/venv/bin/hermes")


def jobs_map() -> dict:
    p = Path.home() / ".hermes" / "cron" / "jobs.json"
    try:
        d = json.loads(p.read_text())
    except Exception:
        return {}
    arr = d if isinstance(d, list) else d.get("jobs", [])
    return {j.get("id"): j for j in arr if isinstance(j, dict)}


def job_line(j: dict | None) -> str:
    if not j:
        return "no-job"
    return f"{'active' if j.get('enabled') else 'paused'} {j.get('schedule', {}).get('display', '')}"


def session_ok(state_path: str | None) -> str:
    p = expand(state_path)
    if not p or not Path(p).exists():
        return "NO_STATE"
    try:
        cookies = json.loads(Path(p).read_text()).get("cookies", [])
        jar = "; ".join(f"{c['name']}={c['value']}" for c in cookies if "threads.com" in c.get("domain", ""))
        req = urllib.request.Request("https://www.threads.com/", headers={"User-Agent": UA, "Cookie": jar})
        with urllib.request.urlopen(req, timeout=25) as r:
            body = r.read(6000).decode("utf-8", "replace")
            if "Log in or sign up" in body:
                return "EXPIRED"
            return "OK"
    except Exception as e:
        return f"ERR {type(e).__name__}"


def queue_count(name: str, acct: dict) -> str:
    role = acct.get("role")
    if role == "queue":
        qf, sf = expand(acct.get("queue")), expand(acct.get("dir")) + "/queue_state.json"
        try:
            q = json.loads(Path(qf).read_text())
            done = set(json.loads(Path(sf).read_text()).get("done", [])) if Path(sf).exists() else set()
            left = [b for b in q if b.get("id") not in done]
            return f"{len(left)}/{len(q)} pending"
        except Exception:
            return "queue?"
    if role == "promo":
        try:
            st = json.loads((Path(expand(acct["dir"])) / "promo_state.json").read_text())
            return f"index {st.get('i', 0)}"
        except Exception:
            return "no-state"
    if role == "reply":
        try:
            q = json.loads((Path(expand(acct["dir"])) / "comments.json").read_text())
            return f"{len(q)} live"
        except Exception:
            return "0 live"
    return "-"


def cmd_list(reg: dict) -> int:
    jm = jobs_map()
    print(f"{'AKUN':10} {'ROLE':6} {'JOB':12} {'STATE':8} ANTREAN")
    for name, a in reg.items():
        if name.startswith("_"):
            continue
        print(f"{name:10} {a.get('role',''):6} {job_line(jm.get(a.get('job'))):12} "
              f"{session_ok(a.get('state')):8} {queue_count(name, a)}")
    return 0


def cmd_status(reg: dict, name: str) -> int:
    a = reg.get(name)
    if not a:
        print("akun tidak ada di registry:", name)
        return 2
    j = jobs_map().get(a.get("job"))
    print(f"akun     : {name} ({a.get('role')})")
    print(f"dir      : {expand(a.get('dir'))}")
    print(f"job      : {a.get('job')} -> {job_line(j)}")
    print(f"sesi     : {session_ok(a.get('state'))}  ({expand(a.get('state'))})")
    print(f"antrean  : {queue_count(name, a)}")
    return 0


def cmd_check(reg: dict, name: str) -> int:
    a = reg.get(name) or {}
    s = session_ok(a.get("state"))
    print(f"{name}: {s}")
    return 0 if s == "OK" else 1


def cmd_post_next(reg: dict, name: str) -> int:
    a = reg.get(name)
    if not a:
        print("akun tidak ada di registry:", name)
        return 2
    if a.get("role") == "reply":
        print("tolong jangan pakai post-next untuk role reply (pakai daemon).")
        return 2
    runner = expand(a.get("runner"))
    if not runner or not Path(runner).exists():
        print("runner tidak ada:", runner)
        return 2
    env = dict(os.environ)
    py = expand(a.get("python") or "~/.hermes/hermes-agent/venv/bin/python")
    if not Path(py).exists():
        py = sys.executable
    r = subprocess.run([py, runner], cwd=expand(a.get("dir")), env=env)
    return r.returncode


def cmd_job(reg: dict, name: str, action: str) -> int:
    a = reg.get(name)
    if not a or not a.get("job"):
        print("job tidak ada untuk:", name)
        return 2
    hb = hermes_bin(reg)
    r = subprocess.run([hb, "cron", action, a["job"]], text=True, capture_output=True)
    print((r.stdout or r.stderr).strip())
    return r.returncode


def main(argv: list[str]) -> int:
    reg = load_reg()
    if len(argv) < 2 or argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        return 1
    cmd = argv[1]
    if cmd == "list":
        return cmd_list(reg)
    name = argv[2] if len(argv) > 2 else ""
    if cmd == "status":
        return cmd_status(reg, name)
    if cmd == "check":
        return cmd_check(reg, name)
    if cmd == "post-next":
        return cmd_post_next(reg, name)
    if cmd in ("pause", "resume"):
        return cmd_job(reg, name, cmd)
    print("perintah tidak dikenal:", cmd)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
