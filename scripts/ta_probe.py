#!/usr/bin/env python3
"""Sonde de couverture Tripadvisor.

  python scripts/ta_probe.py            apparie les adherents, ecrit les identifiants
  python scripts/ta_probe.py --dry      montre les requetes sans appeler l'API

Repond a la seule question qui tranche avant d'investir : combien des adherents
suivis sont reellement trouvables ? Le rapport distingue l'appariement certain
(un seul candidat, nom identique) de l'appariement douteux (plusieurs candidats),
qui demande un arbitrage humain plutot qu'une devinette.
"""
import sys, os, json, time, pathlib, difflib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from core import store                      # noqa: E402
from core.config import ENTITIES            # noqa: E402
from collectors import tripadvisor as TA    # noqa: E402

DRY = "--dry" in sys.argv


def norm(s):
    return "".join(c for c in str(s).lower() if c.isalnum() or c == " ").strip()


def main():
    noms = ENTITIES.get("members_press_watchlist", [])
    print(f"adherents a apparier : {len(noms)}")
    if not TA.key() and not DRY:
        print("\nTRIPADVISOR_API_KEY absente du .env.")
        print("La cle se demande en libre-service sur tripadvisor.com/developers")
        print("puis se colle dans .env sous la forme TRIPADVISOR_API_KEY=...")
        print("Pour voir les requetes sans cle : python scripts/ta_probe.py --dry")
        return 1

    certains, douteux, absents, erreurs = {}, {}, [], []
    for i, nom in enumerate(noms, 1):
        if DRY:
            print(f"  [{i:2}/{len(noms)}] recherche : {nom} Martinique")
            continue
        data, h = TA.search(nom)
        if not h.get("ok"):
            erreurs.append((nom, h))
            print(f"  [{i:2}] {nom:32} ECHEC {h}")
            time.sleep(0.4)
            continue
        if not data:
            absents.append(nom)
            print(f"  [{i:2}] {nom:32} introuvable")
        else:
            best = max(data, key=lambda d: difflib.SequenceMatcher(
                None, norm(nom), norm(d.get("name", ""))).ratio())
            score = difflib.SequenceMatcher(None, norm(nom), norm(best.get("name", ""))).ratio()
            cible = certains if (len(data) == 1 or score >= .82) else douteux
            cible[nom] = best.get("location_id")
            print(f"  [{i:2}] {nom:32} {'OK  ' if cible is certains else 'DOUTE'} "
                  f"{best.get('name','')[:34]} (id {best.get('location_id')}, {score:.2f}, "
                  f"{len(data)} candidat(s))")
        time.sleep(0.4)

    if DRY:
        print("\nmode sec : aucune requete envoyee.")
        return 0

    st = store.load_state()
    st["tripadvisor_ids"] = {**st.get("tripadvisor_ids", {}), **certains}
    st["tripadvisor_doubtful"] = douteux
    store.save_state(st)

    n = len(noms)
    print(f"\n--- couverture ---")
    print(f"  appariement certain : {len(certains):3} / {n}  ({100*len(certains)//max(n,1)} %)")
    print(f"  a arbitrer          : {len(douteux):3}")
    print(f"  introuvables        : {len(absents):3}")
    print(f"  erreurs API         : {len(erreurs):3}")
    if erreurs:
        print(f"\n  premiere erreur : {erreurs[0][1]}")
        print("  Un 401 signifie cle invalide, un 404 un chemin d'API a corriger")
        print("  dans config/sources.json (section tripadvisor).")
    print(f"\n  identifiants ecrits dans data/state.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
