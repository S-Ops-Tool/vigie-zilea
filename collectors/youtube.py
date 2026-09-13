"""Collecte YouTube.

Le flux public par identifiant de chaine ne demande AUCUNE cle et aucune
autorisation — c'est la seule source du dispositif dans ce cas. La cle API
Data v3 n'est utile que pour les compteurs de vues exacts ; sans elle, on
collecte quand meme titres et dates.

Angle mort assume : l'onglet Videos exclut les Shorts.
"""
import os, time
import feedparser, requests
from core import store
from core.config import ENTITIES

UA = "Mozilla/5.0 (compatible; VigieBot/1.0)"
API = "https://www.googleapis.com/youtube/v3/videos"


def _stats(video_ids):
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not key or not video_ids:
        return {}
    out = {}
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i + 50]
        try:
            r = requests.get(API, params={
                "part": "statistics,contentDetails",
                "id": ",".join(chunk), "key": key}, timeout=20)
            r.raise_for_status()
            for it in r.json().get("items", []):
                out[it["id"]] = {
                    "views": int(it["statistics"].get("viewCount", 0)),
                    "duration": it["contentDetails"].get("duration", ""),
                }
        except Exception:  # noqa: BLE001
            pass
    return out


def collect(limit_per_channel=15):
    items, snaps, health = [], [], []
    for ch in ENTITIES["youtube_channels"]:
        try:
            d = feedparser.parse(ch["feed"], agent=UA)
        except Exception as e:  # noqa: BLE001
            health.append({"source": "YT:" + ch["name"], "ok": False, "error": type(e).__name__})
            continue
        if not d.entries:
            health.append({"source": "YT:" + ch["name"], "ok": False, "entries": 0,
                           "note": "chaine muette ou identifiant mort"})
            continue
        health.append({"source": "YT:" + ch["name"], "ok": True, "entries": len(d.entries)})
        vids = []
        for e in d.entries[:limit_per_channel]:
            vid = e.get("yt_videoid") or ""
            if not vid:
                continue
            vids.append(vid)
            items.append(store.make_item(
                "video", "yt:" + vid,
                headline=(e.get("title") or "").strip(),
                source=ch["name"], source_id=ch["handle"],
                channel_type=ch["type"],
                versioncreated=(e.get("published") or "")[:10],
                url="https://www.youtube.com/watch?v=" + vid,
                video_id=vid,
            ))
        st = _stats(vids)
        for vid, s in st.items():
            snaps.append({"entity": "yt:" + vid, "metric": "views", "value": s["views"],
                          "meta": {"channel": ch["name"]}})
        time.sleep(0.3)
    return items, snaps, health
