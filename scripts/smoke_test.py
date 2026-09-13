#!/usr/bin/env python3
"""Verifie que la chaine tourne de bout en bout, sans reseau ni cle API."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from core import store, editorial, llm, health
from render import radar, digest

fake = [
    store.make_item("article", "https://ex.test/a1", headline="Le trafic aérien recule au premier semestre",
                    source="RCI Martinique", versioncreated="2026-09-04",
                    url="https://ex.test/a1", body_text="x" * 400),
    store.make_item("article", "https://ex.test/a2", headline="Liquidation judiciaire prononcée pour un réceptif",
                    source="Antilla", versioncreated="2026-09-05",
                    url="https://ex.test/a2", body_text="La procédure collective a été ouverte. " * 20),
    store.make_item("article", "https://ex.test/a3", headline="Sargasses : nouvel épisode d'échouement",
                    source="St Martin Week", versioncreated="2026-09-06",
                    url="https://ex.test/a3", body_text="y" * 400),
]
for it in fake:
    llm.classify(it, dry_run=True)
b = editorial.split(fake)
assert len(b["president"]) == 1, "le routage président n'a pas capté la procédure collective"
assert b["president"][0]["summary"] is None if "summary" in b["president"][0] else True
themes = {i["theme"] for i in fake}
assert "AIR" in themes and "ENV" in themes, f"classement inattendu : {themes}"
for it in b["members"]:
    llm.summarize(it, dry_run=True)
    assert it["summary"] is None and it["summary_status"] == "dry-run"
store.append_snapshots([{"entity": "viator:martinique", "metric": "offer_count", "value": 70, "meta": {}}])
store.append_snapshots([{"entity": "viator:martinique", "metric": "offer_count", "value": 74, "meta": {}}])
d = store.deltas("offer_count")["viator:martinique"]
assert d["delta"] == 4, f"écart attendu 4, obtenu {d}"
hs = health.summarize([{"source": "A", "ok": True}, {"source": "B", "ok": False}])
assert hs == {"queried": 2, "responded": 1, "failed": 1, "failed_names": ["B"]}
digest.render(b["members"], hs, "Semaine test")
out, payload = radar.render()
assert out.exists() and out.stat().st_size > 5000
print("smoke test OK")
print(f"  routage       : {len(b['members'])} adhérents / {len(b['president'])} président")
print(f"  écart calculé : +{d['delta']} activités")
print(f"  radar         : {out} ({out.stat().st_size} octets)")
