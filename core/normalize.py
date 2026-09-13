"""Normalisation des items avant filtrage.

Google News reformate ce qu'il relaie : il suffixe les titres du nom de
l'editeur et remplace l'URL de l'article par une redirection opaque. Les deux
transformations polluent des etapes situees en aval — le suffixe entre dans le
texte compare par les filtres, la redirection s'affiche telle quelle dans le
mail. On defait donc les deux le plus tot possible.
"""
import re, html as _html

# " - martinique.franceantilles.fr", " | Outremers360" : Google News ajoute
# l'editeur apres le titre. Sans ce nettoyage, un article sur des concerts en
# France metropolitaine passe la porte geographique parce que le nom de domaine
# de la source contient "martinique".
_SUFFIX = re.compile(r"\s+[-–|•]\s+[^-–|•]{2,60}$")


def clean_headline(title, source=""):
    t = (title or "").strip()
    if not t:
        return t
    src = (source or "").strip()
    if src:
        for sep in (" - ", " – ", " | ", " • "):
            if t.endswith(sep + src):
                return t[: -len(sep + src)].strip()
    # pas de source connue : on ne coupe que si la queue ressemble a un domaine
    m = _SUFFIX.search(t)
    if m and re.search(r"\.[a-z]{2,6}$", m.group(0).strip(" -–|•")):
        return t[: m.start()].strip()
    return t


def is_gnews(url):
    return "news.google.com" in (url or "")


def resolve(url, session=None, timeout=15):
    """Rend l'URL de l'editeur derriere une redirection Google News.

    Le format recent n'est plus decodable hors ligne : la charge utile est un
    protobuf sans URL en clair. Il faut donc un appel reseau. On ne le fait que
    sur les items qui partent dans l'envoi — une vingtaine par semaine — jamais
    sur les trois cents collectes. En cas d'echec, on garde le lien Google
    News : il fonctionne dans un navigateur, il est seulement laid.
    """
    if not is_gnews(url):
        return url, "direct"
    try:
        import requests
        s = session or requests
        r = s.get(url, headers={"User-Agent": "Mozilla/5.0"},
                  timeout=timeout, allow_redirects=True)
        final = r.url or ""
        if final and "news.google.com" not in final:
            return final, "redirection"
        m = (re.search(r'data-n-au="([^"]+)"', r.text)
             or re.search(r'<a[^>]+href="(https?://(?!news\.google|accounts\.google)[^"]+)"', r.text))
        if m:
            return m.group(1), "extrait du corps"
    except Exception as e:  # noqa: BLE001
        return url, f"echec {type(e).__name__}"
    return url, "non resolue"


def resolve_all(items, cache_key="gnews_urls"):
    """Resout en place, avec cache persistant : une URL resolue une fois ne
    redeclenche jamais d'appel."""
    from . import store
    st = store.load_state()
    cache = st.get(cache_key, {})
    done = 0
    for it in items:
        u = it.get("url") or ""
        if not is_gnews(u):
            continue
        if u in cache:
            it["url"] = cache[u]
            continue
        new, how = resolve(u)
        if new != u:
            cache[u] = new
            it["url"] = new
            done += 1
    st[cache_key] = cache
    store.save_state(st)
    return done


_TRAIL_DOMAIN = re.compile(r"\s+[a-z0-9][a-z0-9.\-]*\.[a-z]{2,6}\s*$", re.I)


def clean_body(text, source=""):
    """Le resume Google News vaut "titre &nbsp;&nbsp; domaine".

    Le domaine y revient une troisieme fois, apres le titre et le champ source.
    C'est par cette porte que trois depeches sur une eruption en Indonesie sont
    entrees dans une revue de presse martiniquaise : le filtre geographique
    lisait "martinique.franceantilles.fr" dans le corps du texte.
    """
    t = _html.unescape(text or "").replace("\u00a0", " ")
    t = re.sub(r"\s+", " ", t).strip()
    src = (source or "").strip()
    if src and t.endswith(src):
        t = t[: -len(src)].strip()
    t = _TRAIL_DOMAIN.sub("", t).strip()
    return t


# Les flux WordPress collent une signature a la fin de chaque resume :
# « L'article X est apparu en premier sur Y », « The post X appeared first on Y ».
# Ce texte n'appartient pas a l'article. Il pesait sur 106 des 799 articles du
# corpus, faussait le classement par mots-cles et polluait la recherche.
_BOILER = [re.compile(p) for p in [
    r"(?is)\bL[\u2019']article\s+.{0,240}?\best apparu en premier sur\b.*$",
    r"(?is)\bCet article\s+.{0,240}?\best apparu en premier sur\b.*$",
    r"(?is)\bLe post\s+.{0,240}?\best apparu en premier\b.*$",
    r"(?is)\bThe post\s+.{0,240}?\bappeared first on\b.*$",
    r"(?is)\bThis (?:article|post)\s+.{0,240}?\b(?:first appeared|appeared first) on\b.*$",
    r"(?is)\bRead more at\b.*$",
    r"(?is)\bLire (?:la suite|l[\u2019']article)\s*(?:sur|:)?.{0,80}$",
]]


def strip_boilerplate(text):
    t = text or ""
    for rx in _BOILER:
        t = rx.sub("", t)
    return re.sub(r"\s+", " ", t).strip()
