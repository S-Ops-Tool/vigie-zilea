"""Carte des provenances : d'ou vient chaque information, et comment elle est etiquetee.

Page autonome, RECALCULEE depuis la configuration. Elle ne peut donc pas mentir :
si un flux est retire de sources.json, il disparait de la page au run suivant.
C'est la meme discipline que pour le radar — rien ne s'edite a la main.
"""
import json, html as H, datetime, collections, pathlib, base64
from core.config import CLIENT, SOURCES, ENTITIES, EDITORIAL, OUT_DIR
from core import taxonomy, store

B = CLIENT["brand"]
LOGO = pathlib.Path(__file__).parent / "templates" / "zilea-logo.png"


def esc(x):
    return H.escape(str(x or ""))


def _logo():
    if not LOGO.exists():
        return ""
    u = "data:image/png;base64," + base64.b64encode(LOGO.read_bytes()).decode()
    return f'<img class="logo" src="{u}" alt="{esc(CLIENT["name"])}" width="280" height="145">'


def _rows(items, cols):
    out = []
    for it in items:
        tds = "".join(f'<td class="{c[2]}">{c[1](it)}</td>' for c in cols)
        out.append(f"<tr>{tds}</tr>")
    return "".join(out)


def _table(items, cols, cls=""):
    th = "".join(f'<th class="{c[2]}">{esc(c[0])}</th>' for c in cols)
    return (f'<div class="tw"><table class="{cls}"><thead><tr>{th}</tr></thead>'
            f"<tbody>{_rows(items, cols)}</tbody></table></div>")


def _link(u, label=None):
    if not u:
        return "—"
    lab = label or u.replace("https://", "").replace("http://", "").rstrip("/")
    if len(lab) > 46:
        lab = lab[:44] + "…"
    return f'<a href="{esc(u)}" target="_blank" rel="noopener">{esc(lab)}</a>'


def _counts():
    try:
        corpus = store.read_corpus()
    except Exception:  # noqa: BLE001
        return {}
    c = collections.Counter(x.get("kind") for x in corpus)
    th = collections.Counter(x.get("theme") for x in corpus)
    fam = collections.Counter(taxonomy.FAMILY.get(x.get("theme")) for x in corpus)
    terr = collections.Counter(x.get("territory") for x in corpus)
    return {"kinds": c, "themes": th, "fam": fam, "terr": terr, "total": len(corpus)}


def build():
    S, E, ED = SOURCES, ENTITIES, EDITORIAL
    st = _counts()
    tot = st.get("total", 0)

    # ── canal 1 : flux de presse ──────────────────────────────────────────
    feeds = sorted(S.get("feeds", []), key=lambda f: (f.get("scope", ""), f["name"]))
    par_scope = collections.Counter(f.get("scope", "?") for f in feeds)
    t_feeds = _table(feeds, [
        ("Média", lambda f: f'<b>{esc(f["name"])}</b>', "nm"),
        ("Périmètre", lambda f: f'<span class="tag">{esc(f.get("scope"))}</span>', ""),
        ("Rythme", lambda f: esc(f.get("cadence")), "mono"),
        ("Flux", lambda f: _link(f.get("url")), "mono sm"),
        ("Vérifié", lambda f: esc(f.get("verified", "—")), "mono sm"),
    ])

    t_gn = _table(S.get("google_news_queries", []), [
        ("Requête", lambda q: f'<code>{esc(q["q"])}</code>', "mono"),
        ("Rythme", lambda q: esc(q.get("cadence")), "mono sm"),
    ])

    t_pages = _table(S.get("pages", []), [
        ("Source", lambda p: f'<b>{esc(p["name"])}</b>', "nm"),
        ("Rythme", lambda p: esc(p.get("cadence")), "mono sm"),
        ("Page", lambda p: _link(p.get("url")), "mono sm"),
        ("Note", lambda p: esc(p.get("note", "")), "sm"),
    ])

    t_alerts = _table(S.get("alerts", []), [
        ("Alerte", lambda a: f'<b>{esc(a["name"])}</b>', "nm"),
        ("Type", lambda a: esc(a.get("kind")), "mono sm"),
        ("Rythme", lambda a: esc(a.get("cadence")), "mono sm"),
        ("Adresse", lambda a: _link(a.get("url")), "mono sm"),
    ])

    MOIS = ["", "janv.", "févr.", "mars", "avr.", "mai", "juin",
            "juil.", "août", "sept.", "oct.", "nov.", "déc."]
    t_cal = _table(S.get("institutional_calendar", []), [
        ("Publication", lambda c: f'<b>{esc(c["name"])}</b>', "nm"),
        ("Parutions", lambda c: " · ".join(MOIS[m] for m in c.get("months", [])), "mono sm"),
        ("Adresse", lambda c: _link(c.get("url")), "mono sm"),
    ])

    t_blocked = _table(S.get("blocked", []), [
        ("Source", lambda b: f'<b>{esc(b["name"])}</b>', "nm"),
        ("Pourquoi", lambda b: esc(b.get("reason")), ""),
        ("Ce qu'on fait", lambda b: esc(b.get("action")), "sm"),
    ])

    # ── canal 2 : vidéo ───────────────────────────────────────────────────
    TYPES = {"adherent": "Adhérent", "institution": "Institution",
             "media": "Média", "tierce": "Chaîne tierce"}
    chans = collections.defaultdict(list)
    for c in E.get("youtube_channels", []):
        chans[c.get("type", "tierce")].append(c)
    bloc_yt = ""
    for k, lab in TYPES.items():
        lst = sorted(chans.get(k, []), key=lambda c: c["name"])
        if not lst:
            continue
        puces = "".join(
            f'<li>{esc(c["name"])}'
            + (f' <a class="ext" href="https://www.youtube.com/channel/{esc(c["channel_id"])}"'
               f' target="_blank" rel="noopener">↗</a>' if c.get("channel_id") else "")
            + "</li>" for c in lst)
        bloc_yt += (f'<div class="grp"><h4>{esc(lab)} <span class="n">{len(lst)}</span></h4>'
                    f'<ul class="cols">{puces}</ul></div>')

    # ── canal 3 : places de marché ────────────────────────────────────────
    t_mkt = _table(E.get("marketplaces", []), [
        ("Plateforme", lambda m: f'<b>{esc(m["name"])}</b>', "nm"),
        ("API", lambda m: esc(m.get("api") or "aucune — lecture du compteur public"), "sm"),
        ("Page Martinique", lambda m: _link(m.get("url")), "mono sm"),
    ])
    t_bench = _table(E.get("benchmark_destinations", []), [
        ("Destination comparée", lambda d: f'<b>{esc(d["name"])}</b>', "nm"),
        ("Viator", lambda d: f'<code>{esc(d.get("viator"))}</code>', "mono sm"),
        ("GetYourGuide", lambda d: f'<code>{esc(d.get("getyourguide"))}</code>', "mono sm"),
        ("Manawa", lambda d: f'<code>{esc(d.get("manawa"))}</code>', "mono sm"),
    ])

    # ── canal 4 : Instagram ───────────────────────────────────────────────
    ig = collections.Counter(a.get("type", "?") for a in E.get("instagram_accounts", []))
    puces_ig = "".join(f'<li>{esc(k)} <span class="n">{v}</span></li>'
                       for k, v in ig.most_common())

    # ── listes de surveillance ────────────────────────────────────────────
    watch = ", ".join(sorted(E.get("members_press_watchlist", [])))
    eco = "".join(f'<li>{esc(x["name"])}'
                  + (f' <a class="ext" href="{esc(x["url"])}" target="_blank" rel="noopener">↗</a>'
                     if x.get("url") else "") + "</li>"
                  for x in E.get("ecosystem_watchlist", []))
    dest = "".join(f'<li>{esc(x["name"])}'
                   + (f' <a class="ext" href="{esc(x["url"])}" target="_blank" rel="noopener">↗</a>'
                      if x.get("url") else "") + "</li>"
                   for x in E.get("destination_watchlist", []))

    # ── classification ────────────────────────────────────────────────────
    nb = {t: len(p) for t, p in taxonomy.RULES}
    SLOT = {"FREQ": "s1", "AIR": "s2", "CROIS": "s3", "ENV": "s4",
            "GOUV": "s5", "DISTRI": "s6", "OFFRE": "brand"}

    def carte(t):
        n = st.get("themes", {}).get(t, 0)
        part = f"{100*n//tot} %" if tot else "—"
        cls = SLOT.get(t, "neutral")
        return (f'<div class="theme {cls}"><div class="bar"></div>'
                f'<div class="tb"><b>{esc(taxonomy.LABELS[t])}</b>'
                f'<span class="meta">{nb.get(t,0)} motifs · {n} items · {part} du corpus</span>'
                f"</div></div>")

    bloc_tour = "".join(carte(t) for t in taxonomy.TOURISME)
    bloc_hors = "".join(carte(t) for t in taxonomy.HORS)
    nc = st.get("themes", {}).get("NC", 0)

    TERR = {"MQ": "Martinique", "CARAIBE": "Caraïbe", "MONDE": "Secteur monde"}
    bloc_terr = "".join(
        f'<div class="terr"><b>{esc(v)}</b>'
        f'<span class="meta">{st.get("terr",{}).get(k,0)} items</span></div>'
        for k, v in TERR.items())

    etapes = [
        ("Nettoyage", "Le titre et le résumé sont débarrassés de ce que les flux y ajoutent : "
                      "suffixe du nom de domaine, signature « est apparu en premier sur »."),
        ("Type d'item", f"Seuls {' et '.join(ED.get('digest_kinds', []))} peuvent partir par mail. "
                        "Les vidéos et l'offre alimentent le radar."),
        ("Fenêtre", f"Publié depuis moins de {ED.get('window_days')} jours. "
                    "La date est recopiée de la source, jamais déduite."),
        ("Thème", "Un thème de la famille tourisme. Le hors-secteur et le sans-étiquette "
                  "sont écartés de l'envoi."),
        ("Territoire", "Territoire Martinique, ou un adhérent nommé dans le titre."),
        ("Doublons", "Une même dépêche arrive par le site du média, son relais social et "
                     "l'agrégateur. Les titres proches sont rapprochés."),
        ("Routage", f"{len(ED.get('president_only_patterns', []))} motifs judiciaires "
                    "orientent un item vers le président seul, avant tout résumé."),
        ("Plancher", f"En dessous de {ED.get('min_items')} items, l'envoi bascule à la semaine "
                     "suivante plutôt que de partir maigre."),
    ]
    bloc_pipe = "".join(
        f'<li><span class="step">{i}</span><div><b>{esc(n)}</b><p>{esc(d)}</p></div></li>'
        for i, (n, d) in enumerate(etapes, 1))

    maj = datetime.date.today().strftime("%d/%m/%Y")
    kinds = st.get("kinds", {})

    kpi = [
        (len(feeds), "flux de presse"),
        (len(S.get("google_news_queries", [])), "requêtes d'agrégateur"),
        (len(S.get("pages", [])) + len(S.get("alerts", [])), "pages et alertes suivies"),
        (len(E.get("youtube_channels", [])), "chaînes vidéo"),
        (len(E.get("marketplaces", [])), "places de marché"),
        (len(E.get("instagram_accounts", [])), "comptes Instagram repérés"),
    ]
    bloc_kpi = "".join(f'<div class="kpi"><span class="v">{v}</span>'
                       f'<span class="l">{esc(l)}</span></div>' for v, l in kpi)

    return TPL.format(
        name=esc(CLIENT["name"]), maj=maj, logo=_logo(),
        kpi=bloc_kpi, feeds=t_feeds,
        scopes=" · ".join(f"{k} ({v})" for k, v in par_scope.most_common()),
        gn=t_gn, gn_note=esc(S.get("_google_news_note", "")),
        pages=t_pages, alerts=t_alerts, cal=t_cal, blocked=t_blocked,
        yt=bloc_yt, mkt=t_mkt, bench=t_bench, ig=puces_ig,
        nb_ig=len(E.get("instagram_accounts", [])),
        watch=esc(watch), nb_watch=len(E.get("members_press_watchlist", [])),
        eco=eco, nb_eco=len(E.get("ecosystem_watchlist", [])),
        dest=dest, nb_dest=len(E.get("destination_watchlist", [])),
        tour=bloc_tour, hors=bloc_hors, terr=bloc_terr, pipe=bloc_pipe,
        nc=nc, nc_part=f"{100*nc//tot} %" if tot else "—",
        total=tot, n_art=kinds.get("article", 0), n_vid=kinds.get("video", 0),
        n_off=kinds.get("offer", 0),
        f_tour=st.get("fam", {}).get("tourisme", 0),
        f_hors=st.get("fam", {}).get("hors", 0),
        brand=B["teal"], brandd=B["teal_deep"], amber=B["amber"],
        display=B["display_font"], body=B["body_font"], mono=B["mono_font"],
    )


def render():
    out = OUT_DIR / "sources.html"
    out.write_text(build(), encoding="utf-8")
    _index()
    return out


def _index():
    """Page d'accueil du site publie.

    GitHub Pages sert le contenu de out/ tel quel : sans index.html, la racine
    renvoie une 404 et le lien qu'on partage ne mene nulle part.
    """
    import datetime
    d = datetime.date.today().strftime("%d/%m/%Y")
    pages = [
        ("radar.html", "Le radar", "Corpus de presse, vid\u00e9os, offre, citations. L'outil de consultation."),
        ("digest.html", "La revue de la semaine", "L'envoi hebdomadaire tel que le recevraient les adh\u00e9rents."),
        ("sources.html", "D'o\u00f9 viennent les informations", "Les 78 sources interrog\u00e9es et les r\u00e8gles de classement."),
    ]
    cartes = "".join(
        f'<a class="c" href="{u}"><b>{t}</b><span>{d2}</span></a>' for u, t, d2 in pages)
    (OUT_DIR / "index.html").write_text(f"""<!doctype html><html lang="fr"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{CLIENT['name']} \u2014 Vigie</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@600;700&family=Public+Sans:wght@400&family=IBM+Plex+Mono:wght@400&display=swap">
<style>
:root{{--g:#F4F9F8;--s:#fff;--i:#12211F;--i2:#3B4B4A;--m:#6D8382;--r:#DCE9E8;--b:{B['teal']};--bd:{B['teal_deep']}}}
@media(prefers-color-scheme:dark){{:root{{--g:#0D1817;--s:#152322;--i:#E7F2F1;--i2:#B6CBC9;--m:#7E9695;--r:#243937;--b:#6CBFBE;--bd:#8FD4D3}}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--g);color:var(--i);font-family:"Public Sans",system-ui,sans-serif;line-height:1.6}}
.w{{max-width:640px;margin:0 auto;padding:0 20px;padding-block:64px 72px}}
img{{width:180px;max-width:50vw;height:auto;border-radius:6px;margin-bottom:20px}}
@media(prefers-color-scheme:dark){{img{{background:#fff;padding:8px 10px}}}}
h1{{font-family:"Poppins",sans-serif;font-weight:700;font-size:34px;line-height:1.1;margin:0 0 8px;letter-spacing:-.02em}}
p.s{{color:var(--i2);margin:0 0 32px}}
.c{{display:flex;flex-direction:column;gap:3px;background:var(--s);border:1px solid var(--r);
 border-radius:12px;padding:17px 19px;margin-bottom:11px;text-decoration:none;color:inherit;
 transition:border-color .15s}}
.c:hover{{border-color:var(--b)}}
.c b{{font-family:"Poppins",sans-serif;font-size:17px}}
.c span{{color:var(--m);font-size:14px}}
footer{{margin-top:34px;font-family:"IBM Plex Mono",monospace;font-size:11.5px;color:var(--m);line-height:1.8}}
</style></head><body><div class="w">
{_logo()}
<h1>Vigie</h1>
<p class="s">Veille du secteur touristique martiniquais. Recalcul\u00e9e chaque lundi \u00e0 6\u00a0h, heure de Martinique.</p>
{cartes}
<footer>Derni\u00e8re mise \u00e0 jour : {d}<br>Aucune relecture humaine. Chaque titre, date et lien est repris tel quel de sa source.</footer>
</div></body></html>""", encoding="utf-8")


TPL = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>D'où viennent les informations — {name}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@600;700&family=Public+Sans:wght@400;600&family=IBM+Plex+Mono:wght@400;600&display=swap">
<style>
:root{{
 --ground:#F4F9F8;--sheet:#FFF;--sunk:#EDF5F4;--ink:#12211F;--ink2:#3B4B4A;--muted:#6D8382;
 --rule:#DCE9E8;--rule2:#EAF3F2;--brand:{brand};--brandd:{brandd};--brands:#E4F5F4;
 --amber:{amber};--ambers:#FDF3E0;--amberd:#8A6212;--neutral:#93A9A8;
 --s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;--s5:#e87ba4;--s6:#008300;
 --display:"{display}",sans-serif;--body:"{body}",system-ui,sans-serif;--mono:"{mono}",monospace;
}}
@media(prefers-color-scheme:dark){{:root:not([data-theme="light"]){{
 --ground:#0D1817;--sheet:#152322;--sunk:#1B2C2B;--ink:#E7F2F1;--ink2:#B6CBC9;--muted:#7E9695;
 --rule:#243937;--rule2:#1E302F;--brand:#6CBFBE;--brandd:#8FD4D3;--brands:#17302F;
 --ambers:#2C2515;--amberd:#F0CE94;--neutral:#6C8382;
}}}}
:root[data-theme="dark"]{{--ground:#0D1817;--sheet:#152322;--sunk:#1B2C2B;--ink:#E7F2F1;
 --ink2:#B6CBC9;--muted:#7E9695;--rule:#243937;--rule2:#1E302F;--brand:#6CBFBE;--brandd:#8FD4D3;
 --brands:#17302F;--ambers:#2C2515;--amberd:#F0CE94;--neutral:#6C8382;}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--ground);color:var(--ink);font-family:var(--body);font-size:15.5px;
 line-height:1.62;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1000px;margin:0 auto;padding:0 20px;padding-block:36px 70px}}
header{{border-bottom:2px solid var(--brand);padding-bottom:22px;margin-bottom:26px;
 display:flex;flex-direction:column;gap:12px}}
.logo{{width:180px;height:auto;max-width:50vw;border-radius:6px}}
@media(prefers-color-scheme:dark){{:root:not([data-theme="light"]) .logo{{background:#fff;padding:8px 10px}}}}
:root[data-theme="dark"] .logo{{background:#fff;padding:8px 10px}}
h1{{font-family:var(--display);font-weight:700;font-size:clamp(28px,5vw,40px);line-height:1.06;
 margin:0;letter-spacing:-.02em;text-wrap:balance}}
.chapo{{margin:0;color:var(--ink2);max-width:64ch}}
.kpis{{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 34px}}
.kpi{{flex:1 1 140px;background:var(--sheet);border:1px solid var(--rule);border-radius:11px;
 padding:13px 15px;display:flex;flex-direction:column;gap:2px}}
.kpi .v{{font-family:var(--display);font-size:26px;font-weight:700;line-height:1;color:var(--brandd)}}
.kpi .l{{font-size:11.5px;color:var(--muted);line-height:1.35}}
section{{margin:0 0 38px}}
h2{{font-family:var(--display);font-weight:600;font-size:21px;margin:0 0 4px;letter-spacing:-.01em;
 display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}}
h2 .n{{font-family:var(--mono);font-size:12px;color:var(--muted);font-weight:400}}
h3{{font-family:var(--display);font-weight:600;font-size:16px;margin:22px 0 6px}}
h4{{font-family:var(--display);font-weight:600;font-size:13.5px;margin:0 0 6px;
 display:flex;gap:8px;align-items:baseline}}
.lede{{color:var(--ink2);margin:0 0 14px;max-width:70ch}}
.tw{{overflow-x:auto;border:1px solid var(--rule);border-radius:12px;background:var(--sheet)}}
table{{width:100%;border-collapse:collapse;font-size:13.5px}}
th,td{{text-align:left;padding:9px 13px;border-bottom:1px solid var(--rule2);vertical-align:top}}
th{{font-family:var(--mono);font-size:9.5px;letter-spacing:.11em;text-transform:uppercase;
 color:var(--muted);font-weight:600;border-bottom:1px solid var(--rule);white-space:nowrap}}
tr:last-child td{{border-bottom:0}}
td.nm{{font-weight:600}} td.mono,.mono{{font-family:var(--mono)}} td.sm,.sm{{font-size:12px}}
code{{font-family:var(--mono);font-size:12px;background:var(--sunk);padding:1px 5px;border-radius:4px}}
a{{color:var(--brandd);text-underline-offset:2px}}
a.ext{{text-decoration:none;color:var(--muted);font-size:11px}}
a.ext:hover{{color:var(--brand)}}
.tag{{font-family:var(--mono);font-size:10.5px;background:var(--brands);color:var(--brandd);
 padding:2px 7px;border-radius:5px;white-space:nowrap}}
.note{{background:var(--brands);border-left:3px solid var(--brand);border-radius:0 8px 8px 0;
 padding:11px 14px;margin:14px 0;font-size:14px;color:var(--ink2)}}
.warn{{background:var(--ambers);border-left:3px solid var(--amber);border-radius:0 8px 8px 0;
 padding:11px 14px;margin:14px 0;font-size:14px;color:var(--ink2)}}
.warn b,.note b{{color:var(--ink)}}
.grp{{margin:0 0 16px}}
.grp .n,h4 .n{{font-family:var(--mono);font-size:11px;color:var(--muted);font-weight:400}}
ul.cols{{margin:0;padding:0;list-style:none;columns:3;column-gap:22px;font-size:13.5px}}
ul.cols li{{break-inside:avoid;padding:2px 0;color:var(--ink2)}}
@media(max-width:760px){{ul.cols{{columns:2}}}}
@media(max-width:460px){{ul.cols{{columns:1}}}}
.fam{{background:var(--sheet);border:1px solid var(--rule);border-radius:12px;padding:16px 18px;
 margin:0 0 12px}}
.theme{{display:flex;gap:12px;align-items:stretch;padding:7px 0;border-bottom:1px solid var(--rule2)}}
.theme:last-child{{border-bottom:0}}
.theme .bar{{width:5px;border-radius:3px;flex:none}}
.theme.s1 .bar{{background:var(--s1)}} .theme.s2 .bar{{background:var(--s2)}}
.theme.s3 .bar{{background:var(--s3)}} .theme.s4 .bar{{background:var(--s4)}}
.theme.s5 .bar{{background:var(--s5)}} .theme.s6 .bar{{background:var(--s6)}}
.theme.brand .bar{{background:var(--brand)}} .theme.neutral .bar{{background:var(--neutral)}}
.tb{{display:flex;flex-direction:column}}
.tb .meta,.terr .meta{{font-family:var(--mono);font-size:11px;color:var(--muted)}}
.terrs{{display:flex;gap:10px;flex-wrap:wrap}}
.terr{{flex:1 1 170px;background:var(--sheet);border:1px solid var(--rule);border-radius:11px;
 padding:12px 14px;display:flex;flex-direction:column}}
ol.pipe{{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:2px}}
ol.pipe li{{display:flex;gap:13px;padding:11px 0;border-bottom:1px solid var(--rule2)}}
ol.pipe li:last-child{{border-bottom:0}}
.step{{flex:none;width:26px;height:26px;border-radius:8px;background:var(--brand);color:#fff;
 font-family:var(--mono);font-size:12px;font-weight:600;display:grid;place-items:center}}
ol.pipe b{{font-family:var(--display);font-size:14.5px}}
ol.pipe p{{margin:2px 0 0;font-size:13.5px;color:var(--ink2)}}
footer{{margin-top:44px;padding-top:20px;border-top:1px solid var(--rule);
 font-family:var(--mono);font-size:11.5px;color:var(--muted);line-height:1.8}}
</style></head><body>
<div class="wrap">

<header>
 {logo}
 <h1>D'où viennent les informations</h1>
 <p class="chapo">Carte des sources du dispositif de veille, et règles de classement.
 Cette page est recalculée depuis la configuration à chaque run : elle ne peut pas
 diverger de ce que le dispositif interroge réellement.</p>
</header>

<div class="kpis">{kpi}</div>

<section>
 <h2>Presse — flux RSS <span class="n">{scopes}</span></h2>
 <p class="lede">Chaque flux est interrogé à son rythme. La date de vérification est celle
 du dernier contrôle manuel de l'adresse — un flux qui change d'URL sans prévenir est la
 panne la plus banale de ce genre de dispositif.</p>
 {feeds}
</section>

<section>
 <h2>Presse — requêtes d'agrégateur</h2>
 <p class="lede">Google News complète les flux là où un média n'en publie pas.
 {gn_note}</p>
 {gn}
 <div class="warn"><b>Le piège évité.</b> Une requête de la forme
 <code>site:domaine-adhérent</code> ne ramène que ce que l'adhérent publie sur lui-même.
 Les requêtes ci-dessus cherchent les mentions <em>et excluent</em> le domaine propre,
 pour mesurer ce que les tiers disent plutôt que ce que l'intéressé raconte.</div>
</section>

<section>
 <h2>Pages institutionnelles suivies <span class="n">relevé direct</span></h2>
 <p class="lede">Sources sans flux, relevées page par page.</p>
 {pages}
</section>

<section>
 <h2>Alertes opérationnelles <span class="n">quotidien</span></h2>
 <p class="lede">Le seul volet à rythme journalier : sargasses, vigilance météo,
 arrêtés sécheresse.</p>
 {alerts}
</section>

<section>
 <h2>Calendrier institutionnel <span class="n">parutions attendues</span></h2>
 <p class="lede">Publications à date fixe. Le dispositif sait quand les attendre,
 ce qui permet de signaler une parution manquante plutôt que de l'ignorer.</p>
 {cal}
</section>

<section>
 <h2>Vidéo — chaînes suivies</h2>
 <p class="lede">Liste fermée. Le flux public d'une chaîne renvoie ses quinze dernières
 vidéos quelle que soit leur date : le premier passage est un rattrapage de catalogue,
 les suivants un débit réel.</p>
 {yt}
</section>

<section>
 <h2>Offre marchande — places de marché</h2>
 <p class="lede">Le compteur d'activités en vente sur la destination est l'indicateur le plus
 robuste du lot : il ne dépend d'aucune déclaration.</p>
 {mkt}
 <h3>Destinations comparées</h3>
 <p class="lede">Les mêmes compteurs, sur les voisines, pour que le chiffre martiniquais
 ait une échelle.</p>
 {bench}
 <div class="note"><b>Piège de géolocalisation.</b> Prix et devises varient selon le pays
 depuis lequel on interroge ces plateformes. La locale et la devise sont fixées une fois
 pour toutes dans la configuration, sans quoi deux relevés ne sont pas comparables.</div>
</section>

<section>
 <h2>Instagram <span class="n">{nb_ig} comptes repérés</span></h2>
 <p class="lede">Aucune donnée n'est collectée à ce stade : lire des comptes tiers exige une
 application Meta et une revue d'application. Les comptes sont identifiés et vérifiés un par un,
 prêts pour le jour où l'autorisation existe.</p>
 <div class="fam"><ul class="cols">{ig}</ul></div>
</section>

<section>
 <h2>Réputation — Tripadvisor <span class="n">en attente de clé</span></h2>
 <p class="lede">Le collecteur est écrit. L'offre libre-service « Discover » donne les détails
 factuels, les notes et les résumés d'avis ; le classement local est réservé à une offre sous
 contrat. C'est donc le nombre d'avis qui portera le suivi hebdomadaire, la note bougeant
 trop lentement.</p>
 <div class="warn"><b>Contrainte d'affichage.</b> Les conditions imposent d'afficher le logo
 Tripadvisor et les bulles de notation à côté des données. Cela contraindra la maquette du
 radar le jour où elles arrivent.</div>
</section>

<section>
 <h2>Sources écartées <span class="n">et pourquoi</span></h2>
 <p class="lede">Une source écartée volontairement vaut mieux qu'une source oubliée.</p>
 {blocked}
</section>

<section>
 <h2>Listes de surveillance</h2>
 <p class="lede">Ce ne sont pas des sources mais des cibles : les noms cherchés dans tout
 ce qui entre.</p>
 <div class="fam"><h4>Adhérents du cluster <span class="n">{nb_watch} noms</span></h4>
 <p class="sm" style="color:var(--ink2);margin:0">{watch}</p></div>
 <div class="fam"><h4>Institutions &amp; écosystème <span class="n">{nb_eco}</span></h4>
 <ul class="cols">{eco}</ul></div>
 <div class="fam"><h4>Destinations concurrentes <span class="n">{nb_dest}</span></h4>
 <ul class="cols">{dest}</ul></div>
</section>

<section>
 <h2>Classification — deux axes indépendants</h2>
 <p class="lede">Le thème dit <em>de quoi</em> il s'agit, le territoire dit <em>où</em>.
 Mélanger les deux était l'erreur d'origine : une nocturne au Parc Astérix est correctement
 classée en fréquentation, elle n'a simplement rien à faire dans un radar martiniquais.</p>

 <h3>Axe 1 — le thème, en deux familles</h3>
 <div class="fam"><h4>Secteur touristique <span class="n">{f_tour} items</span></h4>{tour}</div>
 <div class="fam"><h4>Hors secteur <span class="n">{f_hors} items</span></h4>{hors}</div>
 <div class="note"><b>Sans étiquette : {nc} items, {nc_part} du corpus.</b> Ce qui reste n'a
 réellement pas de sujet identifiable — une carte publiée par un chef d'État, une cyberattaque
 municipale, un journal télévisé. Une part des items n'a qu'un titre et aucun corps de texte :
 c'est le plancher irréductible. Aucun item sans étiquette n'entre dans l'envoi hebdomadaire.</div>

 <h3>Axe 2 — le territoire</h3>
 <div class="terrs">{terr}</div>
 <div class="note">La Martinique l'emporte sur la Caraïbe, qui l'emporte sur le monde :
 un article qui parle des deux est un article martiniquais, parce que c'est l'angle du cluster
 et pas celui du rédacteur.</div>
</section>

<section>
 <h2>Le filtre de la revue <span class="n">huit étapes, dans cet ordre</span></h2>
 <p class="lede">Aucune de ces étapes ne fait appel à un modèle de langage. Le tri est
 entièrement déterministe et lisible : un item écarté peut toujours s'expliquer par la règle
 qui l'a écarté.</p>
 <ol class="pipe">{pipe}</ol>
 <div class="note"><b>Le modèle n'intervient qu'après, et pour une seule chose :</b> écrire un
 résumé de trois phrases, un article à la fois, sans contexte des autres, sans aucun chiffre
 absent du texte fourni. Le titre, la source, la date et l'adresse ne passent jamais par lui —
 ce sont des copies.</div>
</section>

<footer>
 Corpus au {maj} : {total} items — {n_art} articles, {n_vid} vidéos, {n_off} activités.<br>
 Page recalculée depuis config/sources.json, config/entities.json, config/editorial.json
 et core/taxonomy.py. Aucune saisie manuelle.
</footer>

</div></body></html>"""
