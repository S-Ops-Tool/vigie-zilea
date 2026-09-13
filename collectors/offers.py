"""Collecte de l'offre en vente : Viator (API) + compteurs de destination.

Viator est la seule API du dispositif dont la gratuite est ecrite et l'acces
en self-service. Elle sert les trois variables qui font une serie : prix, note,
nombre d'avis. Regle de cache imposee : TTL < 24 h.

GetYourGuide et Manawa ne sont pas accessibles par API (seuil de 100 000 visites
mensuelles cote GYG). On n'en releve que le compteur de destination, qui suffit
pour une serie hebdomadaire.

PIEGE : le prix et la devise varient selon la geolocalisation. La locale de
collecte est fixee ici une fois pour toutes et ne doit jamais changer, sinon la
serie devient incomparable.
"""
import os, re, time
import requests
from core import store
from core.config import ENTITIES

LOCALE = "en-US"
CURRENCY = "USD"
UA = "Mozilla/5.0 (compatible; VigieBot/1.0)"
VIATOR = "https://api.viator.com/partner"


def _headers():
    return {
        "exp-api-key": os.environ.get("VIATOR_API_KEY", ""),
        "Accept": "application/json;version=2.0",
        "Accept-Language": LOCALE,
        "Content-Type": "application/json",
    }


def viator_products(destination_id="4316", limit=100):
    """Niveau affilie : /products/search rend prix, note et nombre d'avis."""
    if not os.environ.get("VIATOR_API_KEY"):
        return [], {"source": "Viator", "ok": False, "note": "pas de cle API"}
    body = {
        "filtering": {"destination": str(destination_id)},
        "sorting": {"sort": "TRAVELER_RATING", "order": "DESCENDING"},
        "pagination": {"start": 1, "count": min(limit, 50)},
        "currency": CURRENCY,
    }
    try:
        r = requests.post(f"{VIATOR}/products/search", json=body, headers=_headers(), timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception as e:  # noqa: BLE001
        return [], {"source": "Viator", "ok": False, "error": type(e).__name__}
    out = []
    for p in data.get("products", []):
        rv = p.get("reviews", {}) or {}
        pr = (p.get("pricing", {}) or {}).get("summary", {}) or {}
        out.append({
            "platform": "Viator",
            "product_id": p.get("productCode", ""),
            "title": p.get("title", ""),
            "url": p.get("productUrl", ""),
            "price": pr.get("fromPrice"),
            "currency": CURRENCY,
            "rating": rv.get("combinedAverageRating"),
            "reviews": rv.get("totalReviews", 0),
            "duration": (p.get("duration", {}) or {}).get("description", ""),
        })
    return out, {"source": "Viator", "ok": True, "entries": len(out)}


COUNT_RX = {
    "getyourguide": re.compile(r"(\d[\d\s\u00a0\u202f,\.]*)\s*(?:results|r\u00e9sultats|activities)", re.I),
    "viator": re.compile(r"(\d+)\s*results", re.I),
    "manawa": re.compile(r"of\s+(\d+)\s+total results", re.I),
}


def destination_count(mp):
    """Compteur d'offre de la destination — un entier stable et datable.
    C'est l'indicateur le plus robuste du lot : il ne depend d'aucune declaration."""
    try:
        r = requests.get(mp["url"], headers={"User-Agent": UA}, timeout=25)
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001
        return None, {"source": mp["name"], "ok": False, "error": type(e).__name__}
    rx = COUNT_RX.get(mp["id"])
    if not rx:
        return None, {"source": mp["name"], "ok": False, "note": "pas de motif"}
    m = rx.search(r.text)
    if not m:
        return None, {"source": mp["name"], "ok": False, "note": "compteur introuvable"}
    digits = re.sub(r"[^\d]", "", m.group(1))
    if not digits:
        # motif mordu sur une occurrence sans chiffre : on le signale en sante,
        # on ne perd pas la collecte deja faite
        return None, {"source": mp["name"], "ok": False, "note": "compteur illisible"}
    n = int(digits)
    return n, {"source": mp["name"], "ok": True, "entries": n}


def collect():
    items, snaps, health = [], [], []
    prods, h = viator_products()
    health.append(h)
    for p in prods:
        items.append(store.make_item(
            "offer", "viator:" + p["product_id"],
            headline=p["title"], source="Viator", source_id="viator",
            url=p["url"], price=p["price"], currency=p["currency"],
            rating=p["rating"], duration=p["duration"], product_id=p["product_id"],
        ))
        snaps.append({"entity": "viator:" + p["product_id"], "metric": "reviews",
                      "value": p["reviews"], "meta": {"price": p["price"], "rating": p["rating"]}})
        if p["price"] is not None:
            snaps.append({"entity": "viator:" + p["product_id"], "metric": "price",
                          "value": p["price"], "meta": {"currency": p["currency"]}})
    for mp in ENTITIES["marketplaces"]:
        n, h = destination_count(mp)
        health.append(h)
        if n is not None:
            snaps.append({"entity": f"{mp['id']}:martinique", "metric": "offer_count", "value": n, "meta": {}})
        time.sleep(1.0)
    for dest in ENTITIES.get("benchmark_destinations", []):
        for mp in ENTITIES["marketplaces"]:
            did = dest.get(mp["id"])
            if not did:
                continue
            url = mp["url"].replace(mp["destination_id"], did)
            n, _ = destination_count({"id": mp["id"], "name": mp["name"], "url": url})
            if n is not None:
                snaps.append({"entity": f"{mp['id']}:{dest['name'].lower()}",
                              "metric": "offer_count", "value": n, "meta": {}})
            time.sleep(1.0)
    return items, snaps, health
