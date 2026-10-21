import json, hashlib
from pathlib import Path

base = Path("/home/agentuser/blooply_promo")
variants = json.loads((base / "variants.json").read_text())
manifest = {}
for v in variants:
    for field in ("media", "p2_media"):
        p = Path(v[field])
        manifest[f"{v['key']}:{field}"] = {
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "chain": v["chain"],
            "file": p.name,
            "size": p.stat().st_size,
        }
(base / "media_manifest.json").write_text(json.dumps(manifest, indent=1))
print(len(manifest), "entries")
for k, m in manifest.items():
    print(k, m["chain"], m["file"], m["size"])
