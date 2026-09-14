#!/usr/bin/env python3
"""Recupere l'adresse Tripadvisor de chaque adherent apparie, une fois.

Pourquoi un script separe : l'appariement gardait l'identifiant mais jetait les
liens. Or un tableau de reputation sans lien vers la fiche oblige a chercher a
la main ce que la donnee designe deja. Les adresses sont rangees dans
data/state.json, a cote des identifiants : elles ne dependent donc pas d'un
releve, et survivent a tout.

Cout : une entite par adherent, une seule fois.
"""
import sys, time, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from core import store                       # noqa: E402
from collectors import tripadvisor as TA      # noqa: E402

if not TA.key():
    print("pas de cle : TRIPADVISOR_API_KEY absent du .env"); sys.exit(1)

ids = store.load_state().get("tripadvisor_ids", {}) or {}
print(f"adherents apparies : {len(ids)}")

meta, echecs = {}, []
for i, (nom, loc) in enumerate(ids.items(), 1):
    if not loc:
        continue
    d, h = TA.catalog_details(loc)
    if not d:
        echecs.append((nom, h))
        print(f"  [{i:2}] {nom:26} ECHEC {h.get('status')}")
        time.sleep(0.3)
        continue
    u = TA.unwrap(d)
    ta = (u.get("urls") or {}).get("tripadvisor") or {}
    lien = ta.get("main") or ""
    note, avis = TA.note_de(d)
    meta[nom] = {"id": loc, "url": lien, "nom_ta": TA.nom_de(d),
                 "note": note, "avis": avis}
    print(f"  [{i:2}] {nom:26} {str(note):>4}/5 {str(avis):>6} avis  {lien[:52]}")
    time.sleep(0.3)

st = store.load_state()
st["tripadvisor_meta"] = {**st.get("tripadvisor_meta", {}), **meta}
store.save_state(st)
print(f"\n{len(meta)} adresse(s) enregistrees dans data/state.json")
if echecs:
    print(f"{len(echecs)} echec(s) : {[n for n, _ in echecs]}")
