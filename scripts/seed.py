#!/usr/bin/env python3
"""Amorce le corpus avec la collecte deja realisee (mars-septembre 2026).

Sans cet amorcage, le premier run affiche un radar vide et aucun ecart : les
series ne commencent qu'au deuxieme relevé. Avec, le dispositif demarre avec
six mois d'historique et le premier ecart tombe des la semaine suivante.
"""
import json, re, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from core import store

SRC = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "data/seed.json")
seed = json.loads(SRC.read_text(encoding="utf-8"))

items = []
for a in seed["articles"]:
    items.append(store.make_item("article", a[4], headline=a[3], source=a[1],
                                 theme=a[2], versioncreated=a[0], url=a[4], body_text=""))
for v in seed["videos"]:
    items.append(store.make_item("video", "yt:" + v[5], headline=v[3], source=v[1],
                                 channel_type=(v[6] if len(v) > 6 else "adherent"), versioncreated=v[0], video_id=v[5],
                                 url="https://www.youtube.com/watch?v=" + v[5]))
for o in seed["offers"]:
    items.append(store.make_item("offer", o[0].lower() + ":" + o[10], headline=o[1], source=o[0],
                                 product_id=o[10], url=o[9], price=o[3], currency=o[4],
                                 rating=o[5] or None, duration=o[7]))

fresh = store.append_items(items)
snaps = []
for o in seed["offers"]:
    snaps.append({"entity": o[0].lower() + ":" + o[10], "metric": "reviews", "value": o[6],
                  "meta": {"price": o[3], "rating": o[5]}})
for k, v in seed["offer_counts"].items():
    snaps.append({"entity": k, "metric": "offer_count", "value": v, "meta": {}})
store.append_snapshots(snaps)

print(f"amorçage : {len(fresh)} items, {len(snaps)} relevés")
print(f"  articles {len(seed['articles'])} · vidéos {len(seed['videos'])} · offres {len(seed['offers'])}")
