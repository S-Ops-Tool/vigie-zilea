"""Regles editoriales. Elles s'appliquent AVANT tout appel au modele.

Un item route vers le president n'est jamais resume, donc il ne peut pas fuiter
par une reformulation. C'est la difference entre filtrer a l'entree et filtrer
a la sortie.
"""
import re, datetime
from .config import EDITORIAL, ENTITIES
from . import taxonomy

PRES = [re.compile(p) for p in EDITORIAL["president_only_patterns"]]
EXCL = [re.compile(p) for p in EDITORIAL["exclude_patterns"]]


def _blob(item):
    return " ".join(str(item.get(k, "")) for k in ("headline", "body_text", "source"))


def route(item):
    """Retourne 'exclude' | 'president' | 'members'."""
    blob = _blob(item)
    for rx in EXCL:
        if rx.search(blob):
            return "exclude"
    for rx in PRES:
        if rx.search(blob):
            return "president"
    return "members"


def split(items):
    buckets = {"members": [], "president": [], "exclude": []}
    for it in items:
        buckets[route(it)].append(it)
    return buckets


def should_send(n_items):
    """Plancher de publication. Sous le seuil, l'envoi bascule plutot que de
    partir maigre — un digest a deux items chaque lundi apprend a ne plus l'ouvrir."""
    floor = EDITORIAL.get("min_items") or 4
    return n_items >= floor


# --- Le filtre de la revue -------------------------------------------------
# Un seul objet decrit ce qui entre dans l'envoi. Le radar l'affiche comme vue
# par defaut et en enonce les regles a l'ecran : on ne doit jamais avoir a lire
# le code pour savoir pourquoi un article est la ou n'y est pas.

WATCH = [re.compile(re.escape(n), re.I)
         for n in ENTITIES.get("members_press_watchlist", [])]
DIGEST_KINDS = set(EDITORIAL.get("digest_kinds") or ["article", "alert"])
WINDOW = EDITORIAL.get("window_days") or 8
SECTOR_CAP = EDITORIAL.get("sector_cap", 5)
SECTOR_THEMES = set(EDITORIAL.get("sector_themes") or ["DISTRI", "AIR", "CROIS", "FREQ"])

FILTRE = {
    "nom": "Vue de la revue",
    "regles": [
        f"articles et alertes seulement — les vidéos et l'offre ne partent pas par mail",
        f"publié depuis moins de {WINDOW} jours",
        "classé dans un thème — les items non classés sont écartés",
        "territoire Martinique, ou un adhérent nommé dans le titre",
        f"plus une rubrique secteur plafonnée à {SECTOR_CAP} items hors Martinique",
        "doublons fusionnés, titres proches rapprochés",
    ],
}


def named_member(item):
    blob = _blob(item)
    return any(rx.search(blob) for rx in WATCH)


def in_window(item, days=None):
    """La date de publication est un champ recopie, jamais deduit."""
    days = WINDOW if days is None else days
    d = str(item.get("versioncreated") or "")[:10]
    try:
        pub = datetime.date.fromisoformat(d)
    except ValueError:
        return False
    return 0 <= (datetime.date.today() - pub).days <= days


def in_sector(item):
    """Le theme appartient-il a la famille tourisme ?

    Le critere d'avant — « porte un theme, quel qu'il soit » — laissait passer
    un proces d'assises des lors qu'une regle l'avait etiquete. Depuis que la
    taxonomie couvre aussi le hors-secteur, la question se pose correctement :
    c'est la famille qui dit si l'article releve du dispositif.
    """
    return taxonomy.FAMILY.get(item.get("theme")) == "tourisme"


def is_relevant(item):
    """Retenu pour la Martinique : un adherent nomme, ou un item du secteur ET local."""
    if named_member(item):
        return True
    return in_sector(item) and item.get("territory") == "MQ"


def is_sector(item):
    """Retenu pour la rubrique secteur : theme utile, hors Martinique."""
    return (item.get("territory") in ("CARAIBE", "MONDE")
            and in_sector(item) and item.get("theme") in SECTOR_THEMES)


def eligible(items, days=None):
    """Retourne (retenus Martinique, retenus secteur, motifs d'ecartement)."""
    mq, sect = [], []
    dropped = {"hors_type": 0, "hors_fenetre": 0, "hors_sujet": 0}
    for it in items:
        if it.get("kind") not in DIGEST_KINDS:
            dropped["hors_type"] += 1
        elif not in_window(it, days):
            dropped["hors_fenetre"] += 1
        elif is_relevant(it):
            mq.append(it)
        elif is_sector(it):
            sect.append(it)
        else:
            dropped["hors_sujet"] += 1
    # la Caraibe passe avant le monde, puis le plus recent
    sect.sort(key=lambda x: (x.get("territory") != "CARAIBE",
                             str(x.get("versioncreated", ""))), reverse=False)
    sect = sect[:SECTOR_CAP]
    return mq, sect, dropped


def _key(title):
    t = re.sub(r"[^a-z0-9 ]+", " ", str(title or "").lower())
    mots = [w for w in t.split() if len(w) > 3]
    return " ".join(sorted(mots)[:8])


def dedupe(items):
    """Une meme depeche arrive par plusieurs canaux. On rapproche aussi les
    titres proches : huit mots significatifs communs suffisent a reconnaitre
    deux redactions de la meme information."""
    seen, out = {}, []
    for it in items:
        k = _key(it.get("headline"))
        if not k:
            out.append(it); continue
        if k in seen:
            seen[k].setdefault("also_in", []).append(it.get("source", ""))
            continue
        seen[k] = it
        out.append(it)
    return out
