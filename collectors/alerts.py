"""Alertes operationnelles — la seule couche quotidienne.

Un bulletin d'echouement a quatre jours n'a aucune valeur releve une semaine
plus tard. Ces sources ne nourrissent pas le radar : elles nourrissent un fil
d'alerte separe.
"""
import feedparser, requests
from core import store
from core.config import SOURCES

UA = "Mozilla/5.0 (compatible; VigieBot/1.0)"


def hurricane():
    d = feedparser.parse("https://www.nhc.noaa.gov/index-at.xml", agent=UA)
    items = []
    for e in d.entries:
        title = (e.get("title") or "").strip()
        if "There are no tropical cyclones" in title:
            continue
        items.append(store.make_item(
            "alert", e.get("link") or title,
            headline=title, source="National Hurricane Center", source_id="nhc",
            versioncreated=(e.get("published") or "")[:16],
            url=e.get("link") or "https://www.nhc.noaa.gov/",
            body_text=(e.get("summary") or "")[:2000], severity="cyclone",
        ))
    return items, {"source": "NHC", "ok": True, "entries": len(items)}


def page_alert(a):
    try:
        r = requests.get(a["url"], headers={"User-Agent": UA}, timeout=25)
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001
        return [], {"source": a["name"], "ok": False, "error": type(e).__name__}
    return [], {"source": a["name"], "ok": True, "note": "page atteinte, extraction a specifier"}


def collect():
    items, health = [], []
    got, h = hurricane()
    items += got
    health.append(h)
    for a in SOURCES.get("alerts", []):
        if a["id"] == "nhc":
            continue
        got, h = page_alert(a)
        items += got
        health.append(h)
    return items, health
