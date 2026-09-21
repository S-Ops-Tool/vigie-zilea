#!/usr/bin/env python3
"""Refabrique une revue deja emise dont les resumes ont echoue.

  python scripts/refaire_revue.py 2026-S39 --essai
  python scripts/refaire_revue.py 2026-S39

Une revue archivee est normalement un document date, qu'on ne retouche pas.
L'exception est etroite : celle-ci est partie avec un message d'erreur technique
a la place de chaque resume. Ce n'est pas un etat du monde qu'on conserverait,
c'est une panne. On la refait a l'identique quant aux articles retenus, leur
ordre et leurs sections ; seuls les resumes changent.

La liste des articles est relue dans le document archive lui-meme, pas
recomposee : refaire la selection donnerait une autre revue.
"""
import re
import sys
import json
import shutil
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from core import store, health, llm                     # noqa: E402
from core.config import DATA_DIR, OUT_DIR               # noqa: E402
from render import digest                               # noqa: E402

STAMP = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
ESSAI = "--essai" in sys.argv
SANS_APPEL = "--sans-appel" in sys.argv   # reprend les resumes deja produits
if not STAMP:
    print("usage : python scripts/refaire_revue.py 2026-S39 [--essai]")
    sys.exit(1)

ARCH = DATA_DIR / "digests"
src = ARCH / f"{STAMP}.html"
if not src.exists():
    print(f"archive introuvable : {src}")
    sys.exit(1)

html = src.read_text(encoding="utf-8")

# le libelle de semaine, repris tel quel
m = re.search(r"<title>[^<]*—\s*([^<]+)</title>", html)
libelle = m.group(1).strip() if m else STAMP
# les adresses des articles, dans l'ordre du document
urls = re.findall(r'<a href="(https?://[^"]+)"', html)
vus, ordre = set(), []
for u in urls:
    if u not in vus:
        vus.add(u)
        ordre.append(u)

corpus = {c.get("url"): c for c in store.read_corpus() if c.get("url")}
items = [corpus[u] for u in ordre if u in corpus]
perdus = [u for u in ordre if u not in corpus]

print(f"revue   : {STAMP}  —  {libelle}")
print(f"articles retrouves : {len(items)} sur {len(ordre)}")
if perdus:
    print(f"  introuvables au corpus : {len(perdus)}")

mq = [i for i in items if i.get("territory") == "MQ"]
secteur = [i for i in items if i.get("territory") != "MQ"]
print(f"  Martinique : {len(mq)}   secteur : {len(secteur)}")

court = [i for i in items if len((i.get("body_text") or "")) < 200]
print(f"  sans matiere suffisante pour un resume : {len(court)}")

if ESSAI:
    print("\nmode essai : aucun appel au modele, aucune ecriture.")
    sys.exit(0)

def _resumes_archives(html):
    """Recupere les resumes deja produits, par adresse d'article.

    Refaire le rendu apres un changement d'affichage ne doit rien couter : le
    travail du modele est dans le document, il suffit de le relire.
    """
    out = {}
    for bloc in html.split('<tr><td style="padding:0 0 16px;">')[1:]:
        m_url = re.search(r'<a href="(https?://[^"]+)"', bloc)
        m_res = re.search(
            r'<p style="margin:0 0 4px;font-size:14px[^>]*>(.*?)</p>', bloc, re.S)
        if m_url and m_res:
            txt = re.sub("<[^>]+>", "", m_res.group(1))
            txt = (txt.replace("&#x27;", "'").replace("&amp;", "&")
                      .replace("&quot;", '"').replace("&lt;", "<")
                      .replace("&gt;", ">").replace("&#39;", "'").strip())
            if txt:
                out[m_url.group(1)] = txt
    return out


if SANS_APPEL:
    deja = _resumes_archives(html)
    for it in mq:
        r = deja.get(it.get("url"))
        if r:
            it["summary"] = r
            it["summary_status"] = "resume \u00b7 1 source"
        else:
            it["summary"] = None
            it["summary_status"] = ""
    print(f"\nresumes repris de l'archive : {sum(1 for i in mq if i.get('summary'))}"
          f" sur {len(mq)}  (aucun appel au modele)")
    hs = health.summarize([])
    digest.render(mq, hs, libelle, sector=secteur)
    for ext in ("html", "txt"):
        src_f, dst = OUT_DIR / f"digest.{ext}", ARCH / f"{STAMP}.{ext}"
        if src_f.exists():
            shutil.copy2(src_f, dst)
    print(f"archive reecrite : {ARCH / (STAMP + '.html')}")
    print("Etape suivante : python run.py --publier")
    sys.exit(0)

print("\nlecture des articles...")
from core import article                                  # noqa: E402
lus, tentes, motifs = article.enrichir(mq)
print(f"  {lus} lus sur {tentes} tentes")
if motifs:
    print("  echecs :", ", ".join(f"{m} x{n}" for m, n in motifs.most_common(5)))

print("\nproduction des resumes...")
faits = 0
for i, it in enumerate(mq, 1):
    llm.summarize(it)
    if it.get("summary"):
        faits += 1
    if i % 10 == 0:
        print(f"  {i}/{len(mq)}")
print(f"resumes produits : {faits} sur {len(mq)}")

pannes = [i for i in mq if str(i.get("summary_status", "")).startswith("echec")]
if pannes:
    print(f"\nECHEC : {len(pannes)} resume(s) en erreur — "
          f"{pannes[0].get('summary_status')}")
    print("Rien n'a ete ecrit. Corrige la cause avant de recommencer.")
    sys.exit(1)

# le texte lu sur les sites des editeurs ne doit pas survivre au rendu
article.rendre(mq)

hs = health.summarize([])
digest.render(mq, hs, libelle, sector=secteur)

ratios = []
for it in mq:
    r, src = it.get("summary"), it.get("body_text") or ""
    if r and src:
        ratios.append(round(100 * len(r) / len(src)))
if ratios:
    ratios.sort()
    print(f"rapport resume/chapeau : median {ratios[len(ratios)//2]} %, max {ratios[-1]} %")

for ext in ("html", "txt"):
    s = OUT_DIR / f"digest.{ext}"
    d = ARCH / f"{STAMP}.{ext}"
    if s.exists():
        if d.exists():
            shutil.copy2(d, ARCH / f"{STAMP}.{ext}.avant_refection")
        shutil.copy2(s, d)

reste = (ARCH / f"{STAMP}.html").read_text(encoding="utf-8").count("echec resume")
print(f"\narchive reecrite : {ARCH / (STAMP + '.html')}")
print(f"messages d'erreur restants : {reste}")
print("Etape suivante : python run.py --publier")
