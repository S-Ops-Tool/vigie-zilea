"""Le seul endroit ou un modele ecrit quelque chose.

Contraintes structurelles, pas des consignes de prompt :
  - un article a la fois, jamais de contexte inter-articles
  - trois phrases maximum
  - aucune donnee chiffree qui ne figure pas dans le texte fourni
  - en cas d'echec ou de texte absent, on ne resume pas : le champ reste vide
    et le radar affiche « pas de resume » plutot que de combler
"""
import os, json
from .config import EDITORIAL
from . import taxonomy

LOCAL = {x.lower() for x in EDITORIAL.get("local_tourism_sources", [])}

SYSTEM = (
    "Tu resumes UN SEUL article de presse pour une revue de presse sectorielle. "
    "Regles absolues : trois phrases maximum ; uniquement des faits presents dans le texte "
    "fourni ; aucun chiffre que le texte ne contient pas ; aucune mise en perspective, "
    "aucune comparaison avec d'autres articles, aucune conclusion. "
    "Si le texte fourni est trop court ou vide, reponds exactement : SANS_RESUME"
)


def _client():
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return None
    from anthropic import Anthropic
    return Anthropic(api_key=key)


def summarize(item, dry_run=False):
    """Renseigne item['summary'] ou le laisse a None. Ne leve jamais."""
    text = (item.get("body_text") or "").strip()
    if len(text) < 200:
        item["summary"] = None
        item["summary_status"] = "source sans descriptif"
        return item
    if dry_run:
        item["summary"] = None
        item["summary_status"] = "dry-run"
        return item
    cli = _client()
    if cli is None:
        item["summary"] = None
        item["summary_status"] = "pas de cle API"
        return item
    cfg = EDITORIAL["summary"]
    try:
        r = cli.messages.create(
            model=cfg["model"],
            max_tokens=300,
            temperature=cfg.get("temperature", 0),
            system=SYSTEM,
            messages=[{"role": "user", "content": f"Titre : {item.get('headline','')}\n\nTexte :\n{text[:6000]}"}],
        )
        out = r.content[0].text.strip()
        if out == "SANS_RESUME" or len(out) < 30:
            item["summary"] = None
            item["summary_status"] = "resume non produit"
        else:
            item["summary"] = out
            item["summary_status"] = "resume · 1 source"
    except Exception as e:  # noqa: BLE001
        item["summary"] = None
        item["summary_status"] = f"echec resume ({type(e).__name__})"
    return item


THEMES = ["FREQ", "AIR", "CROIS", "ENV", "GOUV", "CONC", "DISTRI"]
THEME_HINT = {
    "FREQ": "frequentation, nuitees, economie, emploi, defaillances",
    "AIR": "aerien, compagnies, lignes, aeroport, trafic passagers",
    "CROIS": "croisiere, escales, port, nautisme",
    "ENV": "sargasses, secheresse, eau, meteo, cyclone, qualite des eaux",
    "GOUV": "institutions, CMT, CTM, prefecture, promotion, offre culturelle",
    "CONC": "autre destination caribeenne",
    "DISTRI": "tour-operateurs, agences de voyages, distribution, eductours",
}


def classify(item, dry_run=False):
    """Attribue un theme ET un territoire. Deterministe, aucun appel au modele.

    Le nom de la fonction est trompeur depuis qu'elle ne touche plus au modele :
    elle est conservee pour ne pas casser les appels existants.
    """
    blob = " ".join(str(item.get(k, "")) for k in ("headline", "body_text"))
    t, how = taxonomy.theme(blob)
    # Un titre de video est souvent trop pauvre pour trancher — "Kanawa versus
    # GC32" ne dit rien a une regle. Mais une video publiee par un adherent EST
    # du contenu d'offre : ce n'est pas une deduction sur le contenu, c'est un
    # fait sur la provenance.
    if t == "NC" and item.get("kind") == "video" and item.get("channel_type") == "adherent":
        t, how = "OFFRE", "chaine adherente"
    # Une activite en vente sur une place de marche EST de l'offre : elle n'a
    # pas besoin qu'une regle de vocabulaire le devine. Les 35 activites Viator
    # restaient sans etiquette faute qu'on leur en attribue une.
    if item.get("kind") == "offer" and t == "NC":
        t, how = "OFFRE", "nature de l'item"
    item["theme"] = t
    item["theme_source"] = how
    # Une video d'une chaine d'adherent, d'institution ou de media local EST
    # martiniquaise, meme si son titre ne le dit pas : "Chante Nwel au Grand
    # Port" ne contient pas le mot Martinique. Seules les chaines tierces
    # doivent le prouver dans leur titre — c'est la que se cachent les 38
    # videos Maldives et Seychelles d'Indalo Space.
    ct = item.get("channel_type")
    if item.get("kind") == "video" and ct in ("adherent", "institution", "media"):
        item["territory"] = "MQ"
    else:
        item["territory"] = taxonomy.territory(blob, item.get("source", ""), LOCAL)
    return item


