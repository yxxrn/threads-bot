import json
from pathlib import Path
from datetime import datetime, timezone

BOT = Path(__file__).resolve().parent

# 1) Session check
sess_path = BOT / "session.json"
if not sess_path.exists():
    print("SESSION: NO_SESSION")
else:
    s = json.loads(sess_path.read_text())
    started = datetime.fromisoformat(s["started_at"])
    elapsed = (datetime.now(timezone.utc) - started).total_seconds() / 3600.0
    dur = s.get("duration_hours")
    if dur is None:
        # unlimited session (runs until the user says stop)
        print(f"SESSION: ACTIVE unlimited ({elapsed:.2f}h)")
    elif elapsed >= float(dur):
        print(f"SESSION: EXPIRED ({elapsed:.2f}h / {dur}h)")
    else:
        print(f"SESSION: ACTIVE ({elapsed:.2f}h / {dur}h)")

# 2) Pending queue check
q_path = BOT / "comments.json"
r_path = BOT / "replied_urls.json"
q = json.loads(q_path.read_text()) if q_path.exists() else []
r = json.loads(r_path.read_text()) if r_path.exists() else []
pending = [c for c in q if c.get("url") not in r]
print(f"PENDING: {len(pending)}")
for c in pending:
    print("  -", c.get("lang", "?"), c.get("url"))
