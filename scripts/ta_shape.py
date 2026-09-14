#!/usr/bin/env python3
"""Releve la FORME brute des reponses Terra.

On n'interprete rien : on ecrit le corps de la reponse tel quel. Un compteur a
zero peut vouloir dire 'aucun resultat' comme 'je cherche la liste sous le
mauvais nom de champ' — seul le corps brut departage.

Plusieurs variantes de requete sont essayees dans le meme passage : une
recherche sans resultat ne renvoie aucune entite et ne coute donc rien.
"""
import sys, json, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from core.config import OUT_DIR                 # noqa: E402
from collectors import tripadvisor as TA        # noqa: E402

if not TA.key():
    print("pas de cle : TRIPADVISOR_API_KEY absent du .env"); sys.exit(1)

C = TA.cfg()
ESSAIS = [
    {"query": "Hotel Bakoua", "geo_name": "Martinique", "locale": "fr-FR", "size": 5},
    {"query": "Hotel Bakoua", "locale": "fr-FR", "size": 5},
    {"query": "Bakoua", "country_code": "MQ", "locale": "fr-FR", "size": 5},
    {"query": "Habitation Clement", "geo_name": "Martinique", "locale": "en-US", "size": 5},
]

rapport = []
gagnant = None
for i, params in enumerate(ESSAIS, 1):
    try:
        r = TA._get(C.get("search_path", "/locations/search"), params)
        try:
            corps = r.json()
        except Exception:                                    # noqa: BLE001
            corps = {"_texte": r.text[:1500]}
        etat = r.status_code
    except Exception as e:                                   # noqa: BLE001
        corps, etat = {"_exception": type(e).__name__, "_msg": str(e)[:300]}, None
    clefs = sorted(corps.keys()) if isinstance(corps, dict) else f"liste[{len(corps)}]"
    print(f"[{i}] {params} -> {etat} | racine : {clefs}")
    rapport.append({"params": params, "status": etat, "corps": corps})
    if etat == 200 and gagnant is None and (
            (isinstance(corps, list) and corps)
            or (isinstance(corps, dict) and any(
                isinstance(v, list) and v for v in corps.values()))):
        gagnant = (params, corps)

fiche = None
if gagnant:
    _, corps = gagnant
    lst = corps if isinstance(corps, list) else next(
        v for v in corps.values() if isinstance(v, list) and v)
    prem = lst[0]
    print(f"\npremier candidat, champs : {sorted(prem.keys()) if isinstance(prem, dict) else type(prem)}")
    loc = None
    if isinstance(prem, dict):
        for k in ("location_id", "locationId", "id", "locationID"):
            if prem.get(k):
                loc = prem[k]; break
    print(f"identifiant : {loc}")
    if loc:
        r = TA._get(C.get("details_path", "/locations/{id}").replace("{id}", str(loc)),
                    {"locale": "fr-FR"})
        try:
            fiche = r.json()
        except Exception:                                    # noqa: BLE001
            fiche = {"_texte": r.text[:1500]}
        print(f"fiche -> {r.status_code} | champs : "
              f"{sorted(fiche.keys()) if isinstance(fiche, dict) else type(fiche)}")

out = OUT_DIR / "ta_shape.json"
out.write_text(json.dumps({"essais": rapport, "fiche": fiche},
                          ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nreponses brutes ecrites dans {out}")
