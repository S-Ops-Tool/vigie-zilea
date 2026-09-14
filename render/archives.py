"""Les revues deja emises, telles qu'elles sont parties.

Une revue publiee est un document date : on ne la regenere pas, on la republie
a l'identique. La page se construit sur les fiches .json ecrites au moment de
l'archivage, jamais sur une relecture du HTML rendu.
"""
import json, html as H, datetime, pathlib, shutil, base64
from core.config import CLIENT, DATA_DIR, OUT_DIR

B = CLIENT["brand"]
ARCHIVE = DATA_DIR / "digests"
PUBLIC = OUT_DIR / "revues"
LOGO = pathlib.Path(__file__).parent / "templates" / "zilea-logo.png"

MOIS = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre"]


def esc(x):
    return H.escape(str(x or ""))


def _logo():
    if not LOGO.exists():
        return ""
    u = "data:image/png;base64," + base64.b64encode(LOGO.read_bytes()).decode()
    return f'<img src="{u}" alt="{esc(CLIENT["name"])}" width="280" height="145">'


def _fiches():
    """Une entree par revue archivee, la plus recente en tete.

    Une revue sans fiche .json (archivee avant que la fiche existe) reste
    listee : son libelle est alors relu dans le <title> du document, qui est
    ecrit par le meme rendu et donc fiable.
    """
    out = []
    if not ARCHIVE.exists():
        return out
    for doc in sorted(ARCHIVE.glob("*.html"), reverse=True):
        fiche = doc.with_suffix(".json")
        if fiche.exists():
            d = json.loads(fiche.read_text(encoding="utf-8"))
        else:
            t = doc.read_text(encoding="utf-8")
            i, j = t.find("<title>"), t.find("</title>")
            lib = t[i + 7:j].split("—")[-1].strip() if 0 <= i < j else doc.stem
            d = {"stamp": doc.stem, "libelle": lib, "items": None,
                 "secteur": None, "emise": None}
        d["fichier"] = doc
        out.append(d)
    return out


def _date_longue(iso):
    if not iso:
        return ""
    d = datetime.date.fromisoformat(iso)
    return f"{d.day} {MOIS[d.month]} {d.year}"


def _carte(d):
    lien = f"revues/{d['stamp']}.html"
    if d.get("items") is None:
        detail = "revue archivée"
    else:
        detail = f"{d['items']} article{'s' if d['items'] > 1 else ''} adhérents"
        if d.get("secteur"):
            detail += f" · {d['secteur']} secteur"
    if d.get("emise"):
        detail += f" · émise le {_date_longue(d['emise'])}"
    return (f'<a class="c" href="{lien}"><b>{esc(d["libelle"])}</b>'
            f'<span>{esc(detail)}</span></a>')


def render():
    """Republie chaque revue archivee et ecrit la page qui les liste."""
    fiches = _fiches()
    PUBLIC.mkdir(parents=True, exist_ok=True)
    for d in fiches:
        shutil.copy2(d["fichier"], PUBLIC / f"{d['stamp']}.html")

    if fiches:
        corps = "".join(_carte(d) for d in fiches)
        intro = ("Chaque revue est conservée telle qu'elle a été émise. "
                 "Ni retouchée, ni recalculée.")
    else:
        corps = ('<p class="vide">Aucune revue archivée pour le moment. '
                 "La première y figurera dès le prochain envoi.</p>")
        intro = "Les revues hebdomadaires s'y accumulent au fil des semaines."

    out = OUT_DIR / "archives.html"
    out.write_text(f"""<!doctype html><html lang="fr"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(CLIENT['name'])} — Revues passées</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@600;700&family=Public+Sans:wght@400&family=IBM+Plex+Mono:wght@400&display=swap">
<style>
:root{{--g:#F4F9F8;--s:#fff;--i:#12211F;--i2:#3B4B4A;--m:#6D8382;--r:#DCE9E8;--b:{B['teal']}}}
@media(prefers-color-scheme:dark){{:root{{--g:#0D1817;--s:#152322;--i:#E7F2F1;--i2:#B6CBC9;--m:#7E9695;--r:#243937;--b:#6CBFBE}}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--g);color:var(--i);font-family:"Public Sans",system-ui,sans-serif;line-height:1.6}}
.w{{max-width:640px;margin:0 auto;padding:0 20px;padding-block:56px 72px}}
img{{width:150px;max-width:44vw;height:auto;border-radius:6px;margin-bottom:18px}}
@media(prefers-color-scheme:dark){{img{{background:#fff;padding:8px 10px}}}}
a.back{{display:inline-block;margin-bottom:22px;color:var(--m);font-size:14px;text-decoration:none}}
a.back:hover{{color:var(--b)}}
h1{{font-family:"Poppins",sans-serif;font-weight:700;font-size:32px;line-height:1.1;margin:0 0 8px;letter-spacing:-.02em}}
p.s{{color:var(--i2);margin:0 0 30px}}
p.vide{{color:var(--m);background:var(--s);border:1px dashed var(--r);border-radius:12px;padding:20px}}
.c{{display:flex;flex-direction:column;gap:3px;background:var(--s);border:1px solid var(--r);
 border-radius:12px;padding:17px 19px;margin-bottom:11px;text-decoration:none;color:inherit;
 transition:border-color .15s}}
.c:hover{{border-color:var(--b)}}
.c b{{font-family:"Poppins",sans-serif;font-size:17px}}
.c span{{color:var(--m);font-size:14px}}
footer{{margin-top:34px;font-family:"IBM Plex Mono",monospace;font-size:11.5px;color:var(--m);line-height:1.8}}
</style></head><body><div class="w">
<a class="back" href="index.html">← Vigie</a>
{_logo()}
<h1>Revues passées</h1>
<p class="s">{intro}</p>
{corps}
<footer>Aucune relecture humaine. Chaque titre, date et lien est repris tel quel de sa source.</footer>
</div></body></html>""", encoding="utf-8")
    return len(fiches), out
