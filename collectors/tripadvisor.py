"""Tripadvisor Content API — reputation par adherent.

Pourquoi cette source plutot que Booking : Booking ne connait que l'hebergement,
ce qui laisse dehors les restaurants, distilleries, loueurs, jardins et
prestataires d'activites — la moitie du cluster. Tripadvisor reference les
quatre categories, et son API est en libre-service la ou celle de Booking
exige un contrat de partenaire gere.

Ce que le dispositif en tire : une note, un nombre d'avis et un classement local
par adherent, releves chaque semaine. La valeur n'est pas dans l'etat, elle est
dans l'ecart — un etablissement qui prend quarante avis en un trimestre pendant
que son voisin en prend trois, ca ne se voit que dans une serie.

Contraintes a garder en tete :
  - la cle se demande en libre-service depuis un compte Tripadvisor existant ;
  - offre Discover : facturation a l'entite, gratuit pour demarrer, 10 000 appels
    par jour, 10 requetes par seconde ;
  - le CLASSEMENT local n'est PAS dans l'offre libre-service : il est reserve a
    l'offre Growth, sous contrat. Le collecteur le releve s'il arrive et
    l'ignore sinon, sans casser la collecte ;
  - l'affichage impose le logo et les bulles de notation a cote des donnees ;
  - la note bouge lentement : c'est le NOMBRE D'AVIS qui porte le signal
    hebdomadaire, pas la note elle-meme.

Les chemins d'API sont en configuration, pas en dur : si Tripadvisor les fait
evoluer, le preflight le dit au premier appel au lieu de collecter du vide.
"""
import os, time, json, urllib.parse
import requests

from core import store
from core.config import SOURCES, ENTITIES

UA = "Mozilla/5.0 (compatible; VigieBot/1.0)"


def cfg():
    return SOURCES.get("tripadvisor") or {}


def key():
    return os.environ.get("TRIPADVISOR_API_KEY", "").strip()


def _get(path, params, timeout=20):
    c = cfg()
    url = c.get("base_url", "https://api.content.tripadvisor.com/api/v1").rstrip("/") + path
    p = dict(params); p["key"] = key()
    r = requests.get(url, params=p, headers={"User-Agent": UA, "accept": "application/json"},
                     timeout=timeout)
    return r


def search(name, extra=""):
    """Cherche un etablissement. Retourne (liste de candidats, diagnostic)."""
    c = cfg()
    q = (name + " " + (extra or c.get("search_suffix", "Martinique"))).strip()
    try:
        r = _get(c.get("search_path", "/location/search"),
                 {"searchQuery": q, "language": c.get("language", "fr")})
    except Exception as e:  # noqa: BLE001
        return [], {"ok": False, "error": type(e).__name__}
    if r.status_code != 200:
        return [], {"ok": False, "status": r.status_code, "body": r.text[:180]}
    data = r.json().get("data", [])
    return data, {"ok": True, "n": len(data)}


def details(location_id):
    c = cfg()
    try:
        r = _get(c.get("details_path", "/location/{id}/details").replace("{id}", str(location_id)),
                 {"language": c.get("language", "fr"), "currency": c.get("currency", "EUR")})
    except Exception as e:  # noqa: BLE001
        return None, {"ok": False, "error": type(e).__name__}
    if r.status_code != 200:
        return None, {"ok": False, "status": r.status_code, "body": r.text[:180]}
    return r.json(), {"ok": True}


def _num(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def collect():
    """Un releve horodate par adherent identifie. Aucune ecriture si pas de cle."""
    items, snaps, health = [], [], []
    if not key():
        health.append({"source": "Tripadvisor", "ok": False, "note": "pas de cle API"})
        return items, snaps, health

    ids = store.load_state().get("tripadvisor_ids", {})
    if not ids:
        health.append({"source": "Tripadvisor", "ok": False,
                       "note": "aucun identifiant apparie — lancer scripts/ta_probe.py"})
        return items, snaps, health

    ok = 0
    for nom, loc in ids.items():
        if not loc:
            continue
        d, h = details(loc)
        if not d:
            health.append({"source": "Tripadvisor:" + nom, **h})
            time.sleep(0.3)
            continue
        ok += 1
        ent = "ta:" + str(loc)
        avis = _num(d.get("num_reviews"))
        note = _num(d.get("rating"))
        rk = (d.get("ranking_data") or {}).get("ranking")
        if avis is not None:
            snaps.append({"entity": ent, "metric": "reviews", "value": int(avis),
                          "meta": {"name": nom, "rating": note, "url": d.get("web_url", "")}})
        if note is not None:
            snaps.append({"entity": ent, "metric": "rating", "value": note, "meta": {"name": nom}})
        if rk is not None:
            snaps.append({"entity": ent, "metric": "ranking", "value": _num(rk) or 0,
                          "meta": {"name": nom}})
        time.sleep(0.3)
    health.append({"source": "Tripadvisor", "ok": ok > 0, "entries": ok})
    return items, snaps, health
