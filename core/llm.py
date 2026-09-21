"""Le seul endroit ou un modele ecrit quelque chose.

Contraintes structurelles, pas des consignes de prompt :
  - un article a la fois, jamais de contexte inter-articles
  - trois phrases maximum
  - aucune donnee chiffree qui ne figure pas dans le texte fourni
  - en cas d'echec ou de texte absent, on ne resume pas : le champ reste vide
    et le radar affiche « pas de resume » plutot que de combler
"""
import os, json, re
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


def _borner(texte, n_source, cfg):
    """Coupe a la phrase pres pour rester sous les bornes.

    La consigne systeme ne borne que le NOMBRE DE PHRASES ; le modele remplit
    l'espace qu'on lui laisse. On garde donc les premieres phrases qui tiennent
    sous le plafond absolu ET sous une fraction de la source. Couper a la
    phrase, jamais au caractere : un resume tronque en plein mot se voit.
    """
    if texte == "SANS_RESUME":
        return texte
    plafond = min(int(cfg.get("max_chars", 320)),
                  int(n_source * float(cfg.get("max_ratio", 0.45))))
    if len(texte) <= plafond:
        return texte
    garde = ""
    for phrase in re.split(r"(?<=[.!?])\s+", texte):
        if len(garde) + len(phrase) + 1 > plafond:
            break
        garde = (garde + " " + phrase).strip()
    return garde or texte[:plafond].rsplit(" ", 1)[0]


def summarize(item, dry_run=False):
    """Renseigne item['summary'] ou le laisse a None. Ne leve jamais."""
    cfg = EDITORIAL["summary"]
    text = (item.get("body_text") or "").strip()
    seuil = cfg.get("min_source_chars", 800)
    if len(text) < seuil:
        # Un chapeau de 300 signes ne se resume pas : trois phrases en font
        # autant. Le rapport median mesure entre le "resume" et sa source
        # etait de 100 % — aucune compression, et une reformulation integrale
        # du seul texte dont on dispose. Le titre et le lien suffisent.
        item["summary"] = None
        item["summary_status"] = ("source sans descriptif" if len(text) < 120
                                  else "")
        item["summary_skip"] = f"source trop courte ({len(text)} < {seuil})"
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
    try:
        # temperature a disparu de messages.create avec la version 1.0 du SDK.
        # L'envoyer levait un TypeError sur CHAQUE article : la revue partait
        # avec un message d'erreur a la place de chaque resume, et le run
        # restait vert. Ce qui tient la bride au modele reste en place : une
        # consigne systeme stricte, un article a la fois, et la reponse
        # SANS_RESUME quand le texte ne permet rien.
        r = cli.messages.create(
            model=cfg["model"],
            max_tokens=300,
            system=SYSTEM,
            messages=[{"role": "user", "content": f"Titre : {item.get('headline','')}\n\nTexte :\n{text[:6000]}"}],
        )
        out = _borner(r.content[0].text.strip(), len(text), cfg)
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


