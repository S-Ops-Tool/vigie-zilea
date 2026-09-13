"""Collecte presse : flux RSS + bridges Google News.

Le titre, la source, la date et l'URL sont RECOPIES du flux. Aucun de ces champs
ne passe par un modele.
"""
import time, urllib.parse
import feedparser
from dateutil import parser as dtparse
from core import store, normalize
from core.config import SOURCES, EDITORIAL

UA = "Mozilla/5.0 (compatible; VigieBot/1.0; +veille sectorielle)"
GN = "https://news.google.com/rss/search?q={q}&hl=fr&gl=FR&ceid=FR:fr"


RELAYS = {x.lower() for x in EDITORIAL.get("excluded_sources", [])}


def _date(entry):
    for k in ("published", "updated", "created"):
        if entry.get(k):
            try:
                return dtparse.parse(entry[k]).date().isoformat()
            except Exception:  # noqa: BLE001
                pass
    return ""


def _text(entry):
    for k in ("summary", "description"):
        if entry.get(k):
            import re
            return re.sub(r"<[^>]+>", " ", entry[k]).strip()
    if entry.get("content"):
        import re
        return re.sub(r"<[^>]+>", " ", entry["content"][0].get("value", "")).strip()
    return ""


def fetch_feed(feed):
    d = feedparser.parse(feed["url"], agent=UA)
    ok = not getattr(d, "bozo", 0) or bool(d.entries)
    items = []
    for e in d.entries:
        url = e.get("link") or ""
        if not url:
            continue
        items.append(store.make_item(
            "article", url,
            headline=(e.get("title") or "").strip(),
            source=feed["name"],
            source_id=feed["id"],
            versioncreated=_date(e),
            url=url,
            body_text=normalize.strip_boilerplate(_text(e)),
            scope=feed.get("scope", ""),
        ))
    return items, ok, len(d.entries)


def fetch_google_news(q):
    url = GN.format(q=urllib.parse.quote(q["q"]))
    d = feedparser.parse(url, agent=UA)
    items = []
    for e in d.entries:
        link = e.get("link") or ""
        if not link:
            continue
        src = ""
        if e.get("source"):
            src = e["source"].get("title", "")
        # Google News remonte aussi des publications Facebook ou X. Ce sont des
        # relais, pas des sources : le meme contenu arrive par ailleurs, et un
        # post social n'a pas de date de publication fiable.
        if src.lower() in RELAYS:
            continue
        items.append(store.make_item(
            "article", link,
            headline=normalize.clean_headline(e.get("title") or "", src),
            source=src or "Google News",
            source_id=q["id"],
            versioncreated=_date(e),
            url=link,
            body_text=normalize.strip_boilerplate(normalize.clean_body(_text(e), src)),
            scope="google-news",
        ))
    return items, bool(d.entries), len(d.entries)


def collect(cadence="weekly"):
    items, health = [], []
    for feed in SOURCES["feeds"]:
        if feed.get("cadence") not in (cadence, "daily") and cadence != "all":
            continue
        try:
            got, ok, n = fetch_feed(feed)
        except Exception as e:  # noqa: BLE001
            got, ok, n = [], False, 0
            health.append({"source": feed["name"], "ok": False, "error": type(e).__name__})
        else:
            health.append({"source": feed["name"], "ok": ok, "entries": n})
        items += got
        time.sleep(0.4)
    for q in SOURCES.get("google_news_queries", []):
        try:
            got, ok, n = fetch_google_news(q)
            health.append({"source": "GN:" + q["id"], "ok": ok, "entries": n})
        except Exception as e:  # noqa: BLE001
            got = []
            health.append({"source": "GN:" + q["id"], "ok": False, "error": type(e).__name__})
        items += got
        time.sleep(0.6)
    return items, health
