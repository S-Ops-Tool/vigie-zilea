"""Controles de sante. Ils sortent dans le pied de page du digest, pas dans un log.

Un outil remis a un tiers se degrade en silence : les flux meurent, les chaines
sont renommees, les comptes basculent en prive. La degradation doit passer sous
les yeux du lecteur.
"""
import json
from .config import DATA_DIR
from . import store

HISTORY = DATA_DIR / "health.jsonl"


def record(rows):
    with open(HISTORY, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": store.now(), "checks": rows}, ensure_ascii=False) + "\n")


def summarize(rows):
    total = len(rows)
    ok = sum(1 for r in rows if r.get("ok"))
    failed = [r["source"] for r in rows if not r.get("ok")]
    return {"queried": total, "responded": ok, "failed": total - ok, "failed_names": failed}


def silent_twice(rows):
    """Sources muettes deux runs de suite — candidates au retrait."""
    if not HISTORY.exists():
        return []
    hist = [json.loads(l) for l in open(HISTORY, encoding="utf-8") if l.strip()]
    if len(hist) < 1:
        return []
    prev_failed = {c["source"] for c in hist[-1]["checks"] if not c.get("ok")}
    now_failed = {r["source"] for r in rows if not r.get("ok")}
    return sorted(prev_failed & now_failed)


def disappeared_offers():
    """Un code produit qui disparait n'est pas une panne : c'est le signal
    qu'un operateur a cesse d'etre distribue."""
    snaps = [s for s in store.read_snapshots() if s["metric"] == "reviews"]
    by_ts = {}
    for s in snaps:
        by_ts.setdefault(s["ts"], set()).add(s["entity"])
    ts = sorted(by_ts)
    if len(ts) < 2:
        return []
    return sorted(by_ts[ts[-2]] - by_ts[ts[-1]])


def to_arbitrate(rows):
    """Alimente la section « decisions en attente » du dossier du dispositif."""
    out = []
    for s in silent_twice(rows):
        out.append({"type": "source muette 2 runs", "subject": s})
    for e in disappeared_offers():
        out.append({"type": "produit disparu du catalogue", "subject": e})
    return out
