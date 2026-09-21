#!/usr/bin/env python3
"""Verifie que la chaine tourne de bout en bout.

Tout est simule, sauf UN appel au modele : c'est le seul endroit ou une
signature de bibliotheque peut changer sous nos pieds, et c'est celui que le
mode sec ne traversait jamais.
"""
import os, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
# Sans cela, la cle vit dans .env et jamais dans l'environnement : le test
# annonce "pas de cle", saute le seul appel reel, et se declare OK. En
# integration la cle arrive par le secret, ici par le fichier.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from core import store, editorial, llm, health
from render import radar, digest

fake = [
    store.make_item("article", "https://ex.test/a1", headline="Le trafic aérien recule au premier semestre",
                    source="RCI Martinique", versioncreated="2026-09-04",
                    url="https://ex.test/a1", body_text="x" * 900),
    store.make_item("article", "https://ex.test/a2", headline="Liquidation judiciaire prononcée pour un réceptif",
                    source="Antilla", versioncreated="2026-09-05",
                    url="https://ex.test/a2", body_text="La procédure collective a été ouverte. " * 20),
    store.make_item("article", "https://ex.test/a3", headline="Sargasses : nouvel épisode d'échouement",
                    source="St Martin Week", versioncreated="2026-09-06",
                    url="https://ex.test/a3", body_text="y" * 900),
]
for it in fake:
    llm.classify(it, dry_run=True)
b = editorial.split(fake)
assert len(b["president"]) == 1, "le routage président n'a pas capté la procédure collective"
assert b["president"][0]["summary"] is None if "summary" in b["president"][0] else True
themes = {i["theme"] for i in fake}
assert "AIR" in themes and "ENV" in themes, f"classement inattendu : {themes}"
# Les articles fictifs depassent le seuil de resume : le mode sec doit donc
# aller jusqu'a la porte du modele et s'arreter la, pas etre ecarte en amont.
for it in b["members"]:
    llm.summarize(it, dry_run=True)
    assert it["summary"] is None, "le mode sec ne doit produire aucun resume"
    assert it["summary_status"] == "dry-run", (
        f"chemin inattendu : {it['summary_status']!r} "
        f"(source de {len(it.get('body_text') or '')} caracteres)")

# Un appel REEL, un seul. Le mode sec ne traverse jamais la bibliotheque du
# modele : il rend la main avant. C'est ce qui a laisse passer un parametre
# retire de l'API, et la revue est partie pendant deux semaines avec un message
# d'erreur a la place de chaque resume. Un article de test, quelques centimes,
# a chaque poussee.
if os.environ.get("ANTHROPIC_API_KEY", "").strip():
    essai = {
        "kind": "article", "headline": "Fr\u00e9quentation h\u00f4teli\u00e8re en hausse",
        "source": "Test", "versioncreated": "2026-01-01",
        "body_text": ("Les h\u00f4tels de Martinique annoncent une fr\u00e9quentation en "
                      "progression sur le premier semestre, port\u00e9e par la client\u00e8le "
                      "hexagonale. Les professionnels restent prudents sur la suite de la "
                      "saison, en raison des incertitudes sur la desserte a\u00e9rienne et du "
                      "retour annonc\u00e9 des sargasses sur les plages du sud."),
    }
    llm.summarize(essai)
    etat = essai.get("summary_status", "")
    assert not etat.startswith("echec"), f"appel au mod\u00e8le en \u00e9chec : {etat}"
    print(f"  r\u00e9sum\u00e9 r\u00e9el  : {etat}")
else:
    print("  r\u00e9sum\u00e9 r\u00e9el  : non test\u00e9 (pas de cl\u00e9)")
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
