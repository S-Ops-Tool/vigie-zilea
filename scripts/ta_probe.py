#!/usr/bin/env python3
"""Sonde de couverture Tripadvisor.

  python scripts/ta_probe.py            apparie les adherents, ecrit les identifiants
  python scripts/ta_probe.py --dry      montre les requetes sans appeler l'API

Repond a la seule question qui tranche avant d'investir : combien des adherents
suivis sont reellement trouvables ? Le rapport distingue l'appariement certain
de l'appariement douteux, qui demande un arbitrage humain plutot qu'une
devinette.

Deux pieges appris sur le terrain :
  - Terra enveloppe chaque resultat dans {"location": {...}} et range le nom
    dans names[]. Lire ces champs a plat renvoie du vide, et la sonde conclut
    a une couverture nulle alors qu'elle n'a rien su lire.
  - un meme nom existe ailleurs dans le monde (ATAO Plongee est aux
    Anses-d'Arlet ET a Hyeres). On verifie donc la geographie, pas seulement
    la ressemblance du nom.
"""
import sys, os, json, time, pathlib, difflib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from core import store                      # noqa: E402
from core.config import ENTITIES, OUT_DIR    # noqa: E402
from collectors import tripadvisor as TA     # noqa: E402

DRY = "--dry" in sys.argv
RELANCE = "--relance" in sys.argv   # ne retente QUE les adherents non trouves
PAYS_ATTENDU = "MQ"


def norm(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s).lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join("".join(c if c.isalnum() else " " for c in s).split())


def score(a, b):
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return 0.0
    base = difflib.SequenceMatcher(None, na, nb).ratio()
    # un nom court entierement contenu dans l'autre est un bon signe :
    # "Bakoua" dans "Hotel Bakoua Martinique" ne doit pas etre penalise
    if na in nb or nb in na:
        base = max(base, 0.85)
    return base


GENERIQUES = {"hotel", "hotels", "residence", "residences", "restaurant", "spa",
              "le", "la", "les", "l", "du", "de", "des", "d", "martinique",
              "trois", "ilets", "fort", "france", "sainte", "anne", "premium",
              "village", "club", "beach", "lagoon", "resort"}


def variantes(nom):
    """Terra cherche par NOM, au mot pres. Un accent ou un mot en trop suffit a
    ne rien trouver. On retente donc quelques formulations avant de conclure a
    une absence — en clair : l'absence doit etre prouvee, pas supposee."""
    base = norm(nom)
    v = [nom, base]
    mots = base.split()
    utiles = [m for m in mots if m not in GENERIQUES]
    if utiles and " ".join(utiles) not in v:
        v.append(" ".join(utiles))
    if len(utiles) > 2:
        v.append(" ".join(utiles[:2]))
    vus, out = set(), []
    for x in v:
        if x and x.lower() not in vus:
            vus.add(x.lower()); out.append(x)
    return out


def main():
    noms = ENTITIES.get("members_press_watchlist", [])
    if RELANCE:
        deja = set(store.load_state().get("tripadvisor_ids", {}))
        noms = [n for n in noms if n not in deja]
        print(f"relance sur les {len(noms)} adherents non trouves")
    print(f"adherents a apparier : {len(noms)}")
    if not TA.key() and not DRY:
        print("\nTRIPADVISOR_API_KEY absente du .env.")
        return 1

    certains, douteux, absents, erreurs, rapport = {}, {}, [], [], []
    brut = None
    for i, nom in enumerate(noms, 1):
        if DRY:
            print(f"  [{i:2}/{len(noms)}] catalogue : {nom}")
            continue
        essais = variantes(nom) if RELANCE else [nom]
        data, h = [], {}
        for q in essais:
            data, h = TA.catalog_search(q)
            if h.get("ok") and data:
                if q != nom:
                    print(f"       (trouve via « {q} »)")
                break
            time.sleep(0.3)
        if not h.get("ok"):
            erreurs.append((nom, h))
            print(f"  [{i:2}] {nom:30} ECHEC {h.get('status')} {str(h.get('body'))[:90]}")
            time.sleep(0.4)
            continue
        if brut is None and data:
            brut = data[0]

        cands = []
        for d in data:
            u = TA.unwrap(d)
            geo = str(u.get("geo") or "")
            note, avis = TA.note_de(d)
            pays = TA.pays_de(d)
            cands.append({"id": TA.loc_id(d), "nom": TA.nom_de(d), "geo": geo or pays,
                          "note": note, "avis": avis, "score": score(nom, TA.nom_de(d)),
                          "ici": pays.upper() == PAYS_ATTENDU})

        ici = [c for c in cands if c["ici"]] or cands
        best = max(ici, key=lambda c: c["score"]) if ici else None

        if not best or not best["id"]:
            absents.append(nom)
            print(f"  [{i:2}] {nom:30} introuvable")
        else:
            sur = best["ici"] and (best["score"] >= .80 or len(ici) == 1 and best["score"] >= .6)
            (certains if sur else douteux)[nom] = best["id"]
            rapport.append({"adherent": nom, "retenu": best, "candidats": cands,
                            "certain": bool(sur)})
            print(f"  [{i:2}] {nom:30} {'OK   ' if sur else 'DOUTE'} "
                  f"{best['nom'][:30]:30} id {best['id']} "
                  f"score {best['score']:.2f} "
                  f"{best['note'] if best['note'] is not None else '-'}/5 "
                  f"{best['avis'] if best['avis'] is not None else '-'} avis "
                  f"[{best['geo'][:18]}]")
        time.sleep(0.4)

    if DRY:
        print("\nmode sec : aucune requete envoyee.")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    f = OUT_DIR / ("ta_couverture_relance.json" if RELANCE else "ta_couverture.json")
    f.write_text(json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8")
    if brut is not None:
        (OUT_DIR / "ta_shape.json").write_text(
            json.dumps(brut, ensure_ascii=False, indent=2), encoding="utf-8")

    st = store.load_state()
    st["tripadvisor_ids"] = {**st.get("tripadvisor_ids", {}), **certains}
    st["tripadvisor_doubtful"] = {**(st.get("tripadvisor_doubtful", {}) if RELANCE else {}),
                                  **douteux}
    store.save_state(st)

    n = len(noms)
    print("\n--- couverture ---")
    print(f"  appariement certain : {len(certains):3} / {n}  ({100*len(certains)//max(n,1)} %)")
    print(f"  a arbitrer          : {len(douteux):3}")
    print(f"  introuvables        : {len(absents):3}")
    print(f"  erreurs API         : {len(erreurs):3}")
    if absents:
        print(f"\n  introuvables : {', '.join(absents[:12])}")
    if erreurs:
        print(f"\n  premiere erreur : {erreurs[0][1]}")
    print(f"\n  detail complet dans {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
