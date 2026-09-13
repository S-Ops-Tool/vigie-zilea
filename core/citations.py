"""Matrice des citations : qui est nomme dans la presse, et quand.

Deux axes de temps, parce qu'ils ne repondent pas a la meme question. Le mois
dit qui existe dans le paysage mediatique ; la semaine dit ce qui bouge. La
serie mensuelle s'appuie sur les six mois d'amorcage et tient debout ; la serie
hebdomadaire ne commence vraiment qu'au premier run continu, et le radar le dit
plutot que de laisser croire a un historique complet.

Trois blocs separes a dessein. Une matrice limitee aux adherents serait presque
vide — trois noms cites sur cinquante et un — et un tableau vide ne transmet pas
ce constat, il donne l'impression que l'outil est casse. Les institutions et les
destinations voisines donnent au tableau sa respiration, et le vide des
adherents se lit alors pour ce qu'il est : une mesure, pas une panne.
"""
import re, datetime, collections
from .config import ENTITIES


def _blob(item):
    return str(item.get("headline", "")) + " " + str(item.get("body_text", "") or "")


def _periods(kind, n):
    """Les n dernieres periodes, de la plus ancienne a la plus recente."""
    today = datetime.date.today()
    out = []
    if kind == "month":
        y, m = today.year, today.month
        for _ in range(n):
            out.append(f"{y:04d}-{m:02d}")
            m -= 1
            if m == 0:
                m = 12; y -= 1
    else:
        lundi = today - datetime.timedelta(days=today.weekday())
        for _ in range(n):
            iso = lundi.isocalendar()
            out.append(f"{iso[0]}-S{iso[1]:02d}")
            lundi -= datetime.timedelta(days=7)
    return list(reversed(out))


def _bucket(date_str, kind):
    d = str(date_str or "")[:10]
    try:
        dt = datetime.date.fromisoformat(d)
    except ValueError:
        return None
    if kind == "month":
        return f"{dt.year:04d}-{dt.month:02d}"
    iso = dt.isocalendar()
    return f"{iso[0]}-S{iso[1]:02d}"


def _groups():
    membres = [{"name": n, "pattern": "(?i)" + re.escape(n)}
               for n in ENTITIES.get("members_press_watchlist", [])]
    return [
        ("adherents", "Adhérents du cluster", membres),
        ("ecosysteme", "Institutions & écosystème", ENTITIES.get("ecosystem_watchlist", [])),
        ("destinations", "Destinations concurrentes", ENTITIES.get("destination_watchlist", [])),
    ]


def build(articles, n_months=12, n_weeks=12):
    """Chaque case porte la liste des articles qui la composent.

    Un compte sans ses sources n'est pas verifiable : c'est le defaut qu'on
    reproche aux tableaux de bord. Les articles cites sont donc embarques une
    fois dans `refs`, et chaque case ne garde que des indices — le meme article
    cite par trois structures n'est stocke qu'une seule fois.
    """
    mois = _periods("month", n_months)
    sems = _periods("week", n_weeks)
    mset, sset = set(mois), set(sems)

    prepped = []
    for a in articles:
        prepped.append((_blob(a), _bucket(a.get("versioncreated"), "month"),
                        _bucket(a.get("versioncreated"), "week"),
                        str(a.get("versioncreated", ""))[:10], a))

    refs, index = [], {}

    def ref_of(a):
        u = a.get("uri")
        if u not in index:
            index[u] = len(refs)
            refs.append({"h": a.get("headline", ""), "s": a.get("source", ""),
                         "d": str(a.get("versioncreated", ""))[:10], "u": a.get("url", "")})
        return index[u]

    groupes = []
    for key, label, entries in _groups():
        lignes = []
        for e in entries:
            rx = re.compile(e["pattern"])
            m = collections.defaultdict(list)
            w = collections.defaultdict(list)
            tous = []
            last = ""
            for blob, bm, bw, d, a in prepped:
                if not rx.search(blob):
                    continue
                i = ref_of(a)
                tous.append(i)
                if d > last:
                    last = d
                if bm in mset:
                    m[bm].append(i)
                if bw in sset:
                    w[bw].append(i)
            lignes.append({"name": e["name"], "url": e.get("url", ""),
                           "total": len(tous), "last": last, "all": tous[:60],
                           "month": {k: v for k, v in m.items()},
                           "week": {k: v for k, v in w.items()}})
        lignes.sort(key=lambda r: (-r["total"], r["name"]))
        cites = sum(1 for r in lignes if r["total"])
        groupes.append({"key": key, "label": label, "rows": lignes,
                        "cited": cites, "tracked": len(lignes)})

    return {"months": mois, "weeks": sems, "groups": groupes, "refs": refs,
            "week_note": "La s\u00e9rie hebdomadaire ne commence qu'au premier run continu : "
                         "avant, le corpus est une s\u00e9lection, pas une collecte semaine apr\u00e8s semaine."}
