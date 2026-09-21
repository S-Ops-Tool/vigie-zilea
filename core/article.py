"""Lecture du corps d'un article, en memoire seulement.

Les flux ne livrent qu'un chapeau — 197 caracteres de mediane sur le corpus.
Resumer un chapeau produit un texte de meme longueur : aucune compression, et
une reformulation integrale du seul texte disponible. Pour qu'un resume ait un
sens, il faut lire l'article.

DECISION STRUCTURANTE : le texte recupere ne touche jamais le disque. Il sert a
produire le resume, puis il est oublie. Le corpus continue de ne conserver que
le chapeau du flux. C'est ce qui permet d'avoir des resumes fabriques sur des
articles entiers SANS que le depot, qui est public, ne contienne des articles
entiers.

On s'annonce, on respecte robots.txt, et on ne demande qu'une page a la fois.
"""
import re
import time
import urllib.parse
import urllib.robotparser

import requests
from bs4 import BeautifulSoup

UA = "VigieBot/1.0 (veille sectorielle ; contact via zilea-martinique.com)"
TIMEOUT = 12
MAX_CHARS = 12000
PAUSE = 1.0                      # une page a la fois, sans presser les serveurs

_ROBOTS = {}                     # domaine -> parseur, pour ne lire qu'une fois
_DERNIER = {}                    # domaine -> horodatage du dernier appel


def _autorise(url):
    """robots.txt fait foi. Illisible ou absent : on s'abstient d'interdire."""
    p = urllib.parse.urlparse(url)
    dom = p.netloc
    if dom not in _ROBOTS:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(f"{p.scheme}://{dom}/robots.txt")
        try:
            rp.read()
        except Exception:                                  # noqa: BLE001
            rp = None
        _ROBOTS[dom] = rp
    rp = _ROBOTS[dom]
    if rp is None:
        return True
    try:
        return rp.can_fetch(UA, url)
    except Exception:                                      # noqa: BLE001
        return True


def _attendre(dom):
    dernier = _DERNIER.get(dom, 0)
    reste = PAUSE - (time.time() - dernier)
    if reste > 0:
        time.sleep(reste)
    _DERNIER[dom] = time.time()


def _paragraphes(bloc):
    """Le texte des <p> du bloc, en ignorant les miettes.

    Mesurer la densite sur TOUT le texte d'un conteneur fait gagner les menus
    et les listes de liens : un bandeau de navigation contient beaucoup de
    caracteres et aucune phrase. On ne compte donc que les paragraphes d'une
    longueur plausible.
    """
    morceaux = []
    for para in bloc.find_all("p"):
        t = para.get_text(" ", strip=True)
        if len(t) >= 60 and t.count(" ") >= 8:
            morceaux.append(t)
    return morceaux


def _texte(html):
    """Le corps de l'article, sans la mecanique de la page."""
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "nav", "aside", "footer", "header",
                   "form", "noscript", "figure", "iframe", "picture"]):
        t.decompose()

    candidats = []
    for bloc in soup.find_all(["article", "main", "div", "section"]):
        ps = _paragraphes(bloc)
        if ps:
            candidats.append((sum(len(x) for x in ps), len(ps), bloc, ps))
    if candidats:
        # le bloc qui porte le plus de texte redactionnel, pas le plus de texte
        candidats.sort(key=lambda c: (c[0], c[1]), reverse=True)
        morceaux = candidats[0][3]
    else:
        morceaux = _paragraphes(soup)

    txt = " ".join(morceaux) if morceaux else soup.get_text(" ", strip=True)
    txt = re.sub(r"\s{2,}", " ", txt).strip()
    return txt[:MAX_CHARS]


def corps(url):
    """Retourne (texte, diagnostic). Ne leve jamais : une lecture qui echoue
    laisse simplement le chapeau du flux en place."""
    if not url or not url.startswith("http"):
        return "", {"ok": False, "motif": "sans adresse"}
    dom = urllib.parse.urlparse(url).netloc
    if not _autorise(url):
        return "", {"ok": False, "motif": "robots.txt"}
    try:
        _attendre(dom)
        r = requests.get(url, headers={"User-Agent": UA,
                                       "Accept-Language": "fr,en;q=0.7"},
                         timeout=TIMEOUT, allow_redirects=True)
    except Exception as e:                                 # noqa: BLE001
        return "", {"ok": False, "motif": type(e).__name__}
    if r.status_code != 200:
        return "", {"ok": False, "motif": f"HTTP {r.status_code}"}
    if "html" not in r.headers.get("Content-Type", ""):
        return "", {"ok": False, "motif": "pas du HTML"}
    try:
        t = _texte(r.text)
    except Exception as e:                                 # noqa: BLE001
        return "", {"ok": False, "motif": "extraction " + type(e).__name__}
    return t, {"ok": bool(t), "n": len(t)}


def enrichir(items, minimum=800):
    """Remplace le chapeau par le corps de l'article, EN MEMOIRE.

    Retourne (nb enrichis, nb tentes, motifs). Les items conservent leur
    chapeau d'origine sous 'body_flux' : c'est lui qui repartira sur disque.
    """
    import collections
    faits, tentes, motifs = 0, 0, collections.Counter()
    for it in items:
        if len(it.get("body_text") or "") >= minimum:
            continue
        tentes += 1
        t, d = corps(it.get("url", ""))
        if d.get("ok") and len(t) > len(it.get("body_text") or ""):
            it["body_flux"] = it.get("body_text") or ""
            it["body_text"] = t
            it["body_source"] = "article"
            faits += 1
        else:
            motifs[d.get("motif", "?")] += 1
    return faits, tentes, motifs


def rendre(items):
    """Remet le chapeau du flux en place. A appeler APRES les resumes :
    rien de ce qui a ete lu sur le site de l'editeur ne doit atteindre le
    disque."""
    for it in items:
        if "body_flux" in it:
            it["body_text"] = it.pop("body_flux")
            it["body_source"] = "flux"
