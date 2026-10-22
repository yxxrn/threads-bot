import json
from pathlib import Path

BASE = Path("/home/agentuser/blooply_promo")
LIB = str(BASE / "media/chain2/c2-library.jpg")
DET = str(BASE / "media/chain2/c2-library-detail.jpg")

vs = json.loads((BASE / "variants.json").read_text())
for v in vs:
    if v["key"] == "C2":
        v["p2_media"] = DET
    else:
        v["p2_media"] = LIB
(BASE / "variants.json").write_text(json.dumps(vs, ensure_ascii=False, indent=1))
for v in vs:
    print(v["key"], "chain", v["chain"], "|", Path(v["media"]).name, "->", Path(v["p2_media"]).name)
