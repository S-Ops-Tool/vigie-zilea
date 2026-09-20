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
    """L'authentification est en configuration, pas en dur.

    L'ancienne Content API prenait la cle en parametre d'URL ; Terra l'exige en
    en-tete x-api-key et refuse tout le reste par un 403 laconique. Garder les
    deux modes evite de reecrire le collecteur au prochain changement.
    """
    c = cfg()
    url = c.get("base_url", "https://terra.tripadvisor.com/api").rstrip("/") + path
    p = dict(params)
    h = {"User-Agent": UA, "accept": "application/json"}
    if c.get("auth", "header") == "header":
        h[c.get("auth_header", "x-api-key")] = key()
    else:
        p["key"] = key()
    return requests.get(url, params=p, headers=h, timeout=timeout)


def _liste(js):
    """Terra n'a pas garde le 'data' de l'ancienne API et la clef varie selon
    l'endpoint. On accepte les formes connues plutot que d'en supposer une."""
    if isinstance(js, list):
        return js
    for k in ("data", "results", "locations", "items", "content"):
        v = js.get(k)
        if isinstance(v, list):
            return v
    return []


def search(name, extra=""):
    """Cherche un etablissement. Retourne (liste de candidats, diagnostic).

    'size' borne le nombre de candidats : la facturation se fait a l'entite
    renvoyee, donc une recherche large coute plus cher qu'une recherche etroite.
    """
    c = cfg()
    params = {c.get("search_param", "query"): name.strip(),
              "locale": c.get("language", "fr"),
              "size": c.get("search_size", 5)}
    if extra or c.get("geo_name"):
        params["geo_name"] = extra or c.get("geo_name")
    try:
        r = _get(c.get("search_path", "/locations/search"), params)
    except Exception as e:  # noqa: BLE001
        return [], {"ok": False, "error": type(e).__name__}
    if r.status_code != 200:
        return [], {"ok": False, "status": r.status_code, "body": r.text[:700]}
    data = _liste(r.json())
    return data, {"ok": True, "n": len(data)}


def unwrap(d):
    """Terra enveloppe chaque resultat dans {"location": {...}}. Sans cette
    ouverture, tous les champs sont lus a vide et l'appariement echoue en
    silence : la sonde annonce alors une couverture nulle alors qu'elle n'a
    simplement rien su lire."""
    if isinstance(d, dict) and isinstance(d.get("location"), dict):
        return d["location"]
    return d if isinstance(d, dict) else {}


def nom_de(d):
    """Le nom vit dans names[], une liste multilingue avec un drapeau primary."""
    ns = unwrap(d).get("names") or []
    for n in ns:
        if isinstance(n, dict) and n.get("primary"):
            return n.get("value") or ""
    return (ns[0].get("value") if ns and isinstance(ns[0], dict) else "") or ""


def pays_de(d):
    """Le code pays vit dans addresses[], pas a la racine."""
    for a in (unwrap(d).get("addresses") or []):
        if isinstance(a, dict) and a.get("country_code"):
            return a["country_code"]
    return ""


def note_de(d):
    """Retourne (note, nombre d'avis) — le catalogue les donne deja."""
    r = unwrap(d).get("overall_rating") or {}
    return r.get("rating"), r.get("count")


def pastille_de(d):
    """Image de notation fournie par Tripadvisor.

    Leurs conditions d'affichage imposent que la note soit accompagnee de leur
    representation graphique, pas seulement d'un chiffre. L'adresse de l'image
    vient de leur reponse : on ne la fabrique pas.
    """
    return (unwrap(d).get("overall_rating") or {}).get("icon_url") or ""


def catalog_search(name, extra=""):
    """Cherche dans TOUT le catalogue, sans filtre d'autorisation.

    C'est la recherche a utiliser pour apparier les adherents : /locations/search
    ne renvoie que les lieux deja inscrits dans la liste autorisee, et retourne
    donc une page vide tant que cette liste l'est. Le catalogue donne
    l'identifiant, le nom, l'adresse et la note, ce qui suffit a decider.
    """
    c = cfg()
    params = {c.get("search_param", "query"): name.strip(),
              "locale": c.get("language", "fr-FR"),
              "size": c.get("search_size", 3)}
    # Le filtre pays ratisse toute l'ile ; geo_name ne ramenerait que les lieux
    # rattaches a la geographie mere "Martinique" et laisserait dehors tout ce
    # qui vit dans une commune (Trois-Ilets, Le Francois, Le Carbet...).
    if c.get("country_code"):
        params["country_code"] = c["country_code"]
    if extra:
        params["geo_name"] = extra
    try:
        r = _get(c.get("catalog_search_path", "/catalog/locations/search"), params)
    except Exception as e:  # noqa: BLE001
        return [], {"ok": False, "error": type(e).__name__}
    if r.status_code != 200:
        return [], {"ok": False, "status": r.status_code, "body": r.text[:700]}
    return _liste(r.json()), {"ok": True, "n": len(_liste(r.json()))}


def loc_id(d):
    """Terra n'a pas garde 'location_id' partout : on accepte les variantes."""
    u = unwrap(d)
    for k in ("id", "location_id", "locationId", "locationID"):
        if u.get(k):
            return u[k]
    return None


def catalog_details(location_id):
    """Fiche catalogue d'un lieu, par identifiant.

    C'est la lecture hebdomadaire : elle donne la note et le nombre d'avis sans
    exiger que le lieu soit inscrit dans la liste des lieux autorises. Une
    entite facturee par adherent et par semaine, contre trois si on repassait
    par une recherche.
    """
    c = cfg()
    path = c.get("catalog_details_path", "/catalog/locations/{id}").replace(
        "{id}", str(location_id))
    try:
        r = _get(path, {"locale": c.get("language", "fr-FR")})
    except Exception as e:  # noqa: BLE001
        return None, {"ok": False, "error": type(e).__name__}
    if r.status_code != 200:
        return None, {"ok": False, "status": r.status_code, "body": r.text[:700]}
    return r.json(), {"ok": True}


def details(location_id):
    c = cfg()
    try:
        r = _get(c.get("details_path", "/locations/{id}").replace("{id}", str(location_id)),
                 {"locale": c.get("language", "fr")})
    except Exception as e:  # noqa: BLE001
        return None, {"ok": False, "error": type(e).__name__}
    if r.status_code != 200:
        return None, {"ok": False, "status": r.status_code, "body": r.text[:700]}
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
        d, h = catalog_details(loc)
        if not d:
            health.append({"source": "Tripadvisor:" + nom, **h})
            time.sleep(0.3)
            continue
        ok += 1
        ent = "ta:" + str(loc)
        # Terra range la note et le nombre d'avis ensemble sous overall_rating,
        # a l'interieur de l'enveloppe {"location": {...}}.
        note, avis = note_de(d)
        note, avis = _num(note), _num(avis)
        u = unwrap(d)
        lien = ((u.get("urls") or {}).get("tripadvisor") or {}).get("main", "")
        rk = None
        if avis is not None:
            snaps.append({"entity": ent, "metric": "reviews", "value": int(avis),
                          "meta": {"name": nom, "rating": note, "url": lien,
                                   "icon": pastille_de(d)}})
        if note is not None:
            snaps.append({"entity": ent, "metric": "rating", "value": note, "meta": {"name": nom}})
        if rk is not None:
            snaps.append({"entity": ent, "metric": "ranking", "value": _num(rk) or 0,
                          "meta": {"name": nom}})
        time.sleep(0.3)
    health.append({"source": "Tripadvisor", "ok": ok > 0, "entries": ok})
    return items, snaps, health
