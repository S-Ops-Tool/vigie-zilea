"""Regeneration du radar.

Le radar n'est pas un fichier qu'on met a jour : c'est une sortie recalculee.
Le gabarit est statique, les donnees sont injectees en un seul bloc JSON.
Rien ne s'y edite a la main, il ne peut donc pas diverger du corpus.
"""
import json, datetime, pathlib
from core.config import CLIENT, ENTITIES, OUT_DIR
from core import store, editorial, taxonomy, citations

TPL = pathlib.Path(__file__).parent / "templates" / "radar.html"


def _mark(item):
    """Chaque item porte l'etat des filtres, calcule une fois, cote serveur.

    Le radar ne recalcule rien : il masque et demasque. C'est ce qui garantit
    que la vue par defaut du radar et le contenu de l'envoi ne peuvent pas
    diverger — meme fonction, meme corpus, meme reponse.
    """
    return dict(item,
                revue=bool(editorial.is_relevant(item) and editorial.in_window(item)),
                mq=item.get("territory") == "MQ")


def _articles_payload(articles, ceiling=250):
    """Tout ce qui concerne la Martinique, plus un echantillon recent du reste."""
    ranked = sorted(articles, key=lambda x: x.get("versioncreated", ""), reverse=True)
    mq = [_mark(a) for a in ranked if a.get("territory") == "MQ"]
    autres = [_mark(a) for a in ranked if a.get("territory") != "MQ"][:ceiling]
    out = sorted(mq + autres, key=lambda x: x.get("versioncreated", ""), reverse=True)
    # Le radar doit afficher EXACTEMENT ce que l'envoi contient, dedoublonnage
    # compris : un ecart de trois items entre les deux vues suffit a faire
    # douter de l'ensemble.
    garde = {id(x) for x in editorial.dedupe([x for x in out if x["revue"]])}
    for x in out:
        if x["revue"] and id(x) not in garde:
            x["revue"] = False
            x["doublon"] = True
    return out


def _reputation():
    """Note et nombre d'avis par adherent, avec l'ecart depuis le releve precedent.

    La table se construit sur les identifiants apparies, pas sur les releves :
    un adherent suivi mais muet cette semaine doit rester visible, sinon on ne
    voit jamais qu'il manque. Tant qu'un seul releve existe, l'ecart est nul —
    c'est normal, la valeur nait de la serie.
    """
    st = store.load_state()
    ids = st.get("tripadvisor_ids", {}) or {}
    # Le lien vit a cote de l'identifiant, pas dans un releve : un tableau reste
    # cliquable meme la semaine ou un adherent n'a pas repondu.
    meta_ta = st.get("tripadvisor_meta", {}) or {}
    av, no = store.deltas("reviews"), store.deltas("rating")
    rows = []
    for nom, loc in ids.items():
        if not loc:
            continue
        ent = "ta:" + str(loc)
        a, n = av.get(ent) or {}, no.get(ent) or {}
        meta = a.get("meta") or {}
        rows.append({
            "nom": nom, "id": loc,
            "avis": a.get("value"), "delta": a.get("delta"),
            "note": n.get("value"),
            "note_delta": n.get("delta"),
            "depuis": a.get("since"),
            # le lien vient du releve, jamais d'une URL reconstruite a partir de
            # l'identifiant : une adresse fabriquee a la main finit par mentir
            "url": (meta_ta.get(nom) or {}).get("url") or meta.get("url") or "",
            "nom_ta": (meta_ta.get(nom) or {}).get("nom_ta") or "",
            "icon": (meta_ta.get(nom) or {}).get("icon") or meta.get("icon") or "",
        })
    rows.sort(key=lambda r: (r["avis"] is None, -(r["avis"] or 0)))
    return rows


CHAMPS_NON_PUBLIES = ("body_text", "body")


def _alleger(items):
    """Retire de la page ce qui n'y est pas affiche mais y serait publie.

    Le texte de presse n'apparaissait nulle part a l'ecran, mais il voyageait
    dans la charge utile : embarque dans le HTML, donc lisible par quiconque
    ouvre le code source de la page. Une page publique ne transporte que ce
    qu'elle montre.
    """
    return [{k: v for k, v in it.items() if k not in CHAMPS_NON_PUBLIES}
            for it in items]


def build_payload():
    corpus = store.read_corpus()
    articles = [c for c in corpus if c["kind"] == "article"]
    videos = [c for c in corpus if c["kind"] == "video"]
    offers = [c for c in corpus if c["kind"] == "offer"]
    return {
        "client": CLIENT,
        "generated": store.now(),
        "period": {"end": datetime.date.today().isoformat()},
        "counts": {
            "articles": len(articles), "videos": len(videos), "offers": len(offers),
            "yt_channels": len(ENTITIES["youtube_channels"]),
            "ig_accounts": len(ENTITIES["instagram_accounts"]),
        },
        # Le plafond ne s'applique PAS aux articles martiniquais.
        # Avec 700 items collectes en une semaine, un plafond global de 400
        # ramenait le radar a cinq jours d'histoire : les six mois d'amorçage
        # disparaissaient derriere l'actualite sectorielle mondiale du jour.
        "articles": _alleger(_articles_payload(articles)),
        "videos": _alleger([_mark(v) for v in sorted(
            videos, key=lambda x: x.get("versioncreated", ""),
            reverse=True)[:500]]),
        # l'ordre est choisi a l'ecran ; ici on garde les plus recemment reperees
        "offers": sorted(offers, key=lambda x: (x.get("collected") or ""),
                         reverse=True)[:200],
        "deltas": {
            "offer_count": store.deltas("offer_count"),
            "reviews": store.deltas("reviews"),
            "rating": store.deltas("rating"),
            "views": store.deltas("views"),
        },
        "reputation": _reputation(),
        # la taxonomie voyage avec les donnees : les libelles affiches et les
        # regles du filtre viennent du meme endroit que le classement
        "taxonomy": {
            "themes": [t for t in taxonomy.THEMES],
            "families": taxonomy.FAMILY,
            "family_labels": taxonomy.FAMILY_LABELS,
            "theme_labels": taxonomy.LABELS,
            "territories": taxonomy.TERRITORIES,
            "territory_labels": taxonomy.TERR_LABELS,
        },
        "filtre": editorial.FILTRE,
        # qui est nomme dans la presse, mois par mois et semaine par semaine
        "citations": citations.build(articles),
        "instagram": ENTITIES["instagram_accounts"],
        "channels": ENTITIES["youtube_channels"],
    }


def render():
    payload = build_payload()
    html = TPL.read_text(encoding="utf-8")
    html = html.replace("/*__PAYLOAD__*/", "window.RADAR = " + json.dumps(payload, ensure_ascii=False) + ";")
    html = html.replace("{{CLIENT_NAME}}", CLIENT["name"])
    for k, v in CLIENT["brand"].items():
        html = html.replace("{{brand." + k + "}}", str(v))
    out = OUT_DIR / "radar.html"
    out.write_text(html, encoding="utf-8")
    return out, payload
