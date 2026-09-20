"""Magasin de donnees.

Deux objets distincts, et c'est la decision d'architecture qui porte tout le reste :

  corpus.jsonl    les items (articles, videos, activites), immuables une fois ecrits
  snapshots.jsonl les COMPTEURS horodates a chaque run

Aucune API concernee ne fournit d'historique : ni Instagram, ni YouTube, ni Viator,
ni Tripadvisor. Un compteur non releve est un compteur perdu. Les ecarts — un
operateur qui decroche, un prix qui grimpe, une chaine qui se reveille — n'existent
que si on a commence a stocker tot.
"""
import json, hashlib, datetime
from .config import DATA_DIR

CORPUS = DATA_DIR / "corpus.jsonl"
SNAPSHOTS = DATA_DIR / "snapshots.jsonl"
STATE = DATA_DIR / "state.json"


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def uri_key(kind, url_or_id):
    return kind + ":" + hashlib.sha1(url_or_id.encode("utf-8")).hexdigest()[:16]


def _read(path):
    if not path.exists():
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def read_corpus():
    return _read(CORPUS)


def read_snapshots():
    return _read(SNAPSHOTS)


def known_keys():
    return {it["uri"] for it in read_corpus()}


EXTRAIT_MAX = 400


def _pour_disque(item):
    """Ce qui part au corpus ne garde qu'un extrait du texte de presse.

    La troncature a lieu a l'ECRITURE, pas a la collecte : les resumes sont
    produits plus tot dans le meme run, sur le texte complet encore en memoire,
    et ne perdent rien. Ce qui est conserve sur disque — donc publie avec le
    depot — redevient un extrait court au lieu d'une reproduction.
    """
    t = item.get("body_text")
    if isinstance(t, str) and len(t) > EXTRAIT_MAX:
        item = dict(item)
        item["body_text"] = t[:EXTRAIT_MAX].rstrip() + "\u2026"
        item["body_tronque"] = True
    return item


def append_items(items):
    """Ajoute uniquement les items inconnus. Retourne ceux reellement ecrits.

    Retourne les items COMPLETS : l'extrait ne concerne que le disque.
    """
    seen = known_keys()
    fresh = [it for it in items if it["uri"] not in seen]
    if fresh:
        with open(CORPUS, "a", encoding="utf-8") as f:
            for it in fresh:
                f.write(json.dumps(_pour_disque(it), ensure_ascii=False) + "\n")
    return fresh


def append_snapshots(rows):
    """rows: [{entity, metric, value, meta}] — l'horodatage est ajoute ici."""
    ts = now()
    with open(SNAPSHOTS, "a", encoding="utf-8") as f:
        for r in rows:
            r = dict(r)
            r["ts"] = ts
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(rows)


def deltas(metric, entity=None):
    """Ecart entre les deux derniers releves d'un compteur. C'est la sortie
    que le radar affiche : l'etat seul n'apprend rien, le mouvement si."""
    rows = [r for r in read_snapshots() if r["metric"] == metric]
    if entity:
        rows = [r for r in rows if r["entity"] == entity]
    by_entity = {}
    for r in sorted(rows, key=lambda x: x["ts"]):
        by_entity.setdefault(r["entity"], []).append(r)
    out = {}
    for ent, series in by_entity.items():
        if len(series) < 2:
            out[ent] = {"value": series[-1]["value"], "delta": None, "since": None}
        else:
            out[ent] = {
                "value": series[-1]["value"],
                "delta": series[-1]["value"] - series[-2]["value"],
                "since": series[-2]["ts"],
            }
    return out


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {}


def save_state(st):
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


def make_item(kind, uri_source, **fields):
    """Item au format ninjs allege. Les champs recopies de la source ne passent
    jamais par le modele : titre, date, source, url sont des copies."""
    item = {
        "uri": uri_key(kind, uri_source),
        "kind": kind,
        "collected": now(),
        "verbatim": ["headline", "source", "versioncreated", "url"],
    }
    item.update(fields)
    return item
