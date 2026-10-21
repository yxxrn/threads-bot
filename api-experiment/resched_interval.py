import json, csv
from datetime import datetime, timedelta, timezone

WIB = timezone(timedelta(hours=7))
BASE = "/home/agentuser/clove"
STEP = timedelta(hours=3, minutes=30)
anchor = datetime(2026, 10, 22, 4, 15, tzinfo=WIB)

q = json.load(open(f"{BASE}/clove_queue.json"))
for b in q:
    if b["id"] >= 7:
        b["due_at"] = (anchor + STEP * (b["id"] - 7)).isoformat()
        b["status"] = "pending"
json.dump(q, open(f"{BASE}/clove_queue.json", "w"), ensure_ascii=False, indent=1)

with open(f"{BASE}/clove_schedule.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "due_at", "kind", "label", "parts", "media"])
    for b in q:
        media = ";".join(m for p in b.get("parts", []) for m in p.get("media", []))
        w.writerow([b["id"], b["due_at"], b["kind"], b["label"], len(b.get("parts", [])), media])

for b in q[:12]:
    print(b["id"], b["due_at"], b["kind"], b["label"])
print("last", q[-1]["id"], q[-1]["due_at"])
