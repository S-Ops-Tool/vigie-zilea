"""Generation de l'envoi hebdomadaire.

Colonne unique 600 px, tableaux et CSS en ligne — ce que les clients de
messagerie exigent. Version texte brut jointe systematiquement.
"""
import datetime, html as H
from core.config import CLIENT, EDITORIAL, OUT_DIR
from core import taxonomy

B = CLIENT["brand"]
LABELS = dict(taxonomy.LABELS)
ORDER = ["ENV", "GOUV", "AIR", "CROIS", "OFFRE", "DISTRI", "FREQ"]


def _item(it):
    prov = " · ".join(x for x in [it.get("source", ""), it.get("versioncreated", "")] if x)
    # Deux natures de "pas de resume" qu'il ne faut pas confondre a l'ecran.
    # "source sans descriptif" renseigne le lecteur : le flux n'a rien fourni.
    # "echec resume (TypeError)" ne renseigne personne, sauf sur notre panne :
    # sa place est dans le releve de sante, pas dans une revue envoyee au
    # client. Un titre seul reste lisible ; un message d'erreur, non.
    # Pas de resume : rien. Aucune mention d'etat n'atteint le lecteur, qu'elle
    # vienne d'une panne ou d'une source trop maigre. Ces libelles servent au
    # releve de sante, ou ils sont lus par quelqu'un qui peut en faire quelque
    # chose. Sous un titre de revue, ils ne font que signaler un manque.
    body = ""
    if it.get("summary"):
        body = f'<p style="margin:0 0 4px;font-size:14px;line-height:1.5;color:#3C4A4A;">{H.escape(it["summary"])}</p>'
    return f"""
    <tr><td style="padding:0 0 16px;">
      <a href="{H.escape(it.get('url',''))}" style="font-family:{B['display_font']},Georgia,serif;font-size:16px;
         line-height:1.3;font-weight:600;color:{B['ink']};text-decoration:none;
         border-bottom:1.5px solid {B['amber']};">{H.escape(it.get('headline',''))}</a>
      <div style="height:6px;"></div>
      {body}
      <div style="font-family:monospace;font-size:10px;color:#6E8484;">{H.escape(prov)}</div>
    </td></tr>"""


def _section(theme, items):
    if not items:
        return ""
    rows = "".join(_item(i) for i in items)
    return f"""
    <tr><td style="padding:18px 22px;border-bottom:1px solid #EAF3F2;">
      <div style="font-size:10.5px;font-weight:700;letter-spacing:.13em;text-transform:uppercase;
           color:{B['teal_deep']};margin-bottom:12px;">{LABELS.get(theme, theme)}
           <span style="float:right;font-family:monospace;font-weight:400;color:#6E8484;">
           {len(items)} item{'s' if len(items) > 1 else ''}</span></div>
      <table width="100%" cellpadding="0" cellspacing="0" border="0">{rows}</table>
    </td></tr>"""


def render(items, health, week_label, issue_no=1, sector=None):
    by_theme = {}
    for it in items:
        by_theme.setdefault(it.get("theme", "FREQ"), []).append(it)
    sections = "".join(_section(t, by_theme.get(t, [])) for t in ORDER)
    # La rubrique secteur est separee et plafonnee : ce qui ne concerne pas la
    # Martinique ne doit jamais se melanger a ce qui la concerne, sous peine de
    # rendre la revue illisible — c'etait le defaut d'origine.
    if sector:
        rows = "".join(_item(i) for i in sector)
        sections += f"""
    <tr><td style="padding:18px 22px;border-top:3px solid {B['amber']};background:#FFFCF6;">
      <div style="font-size:10.5px;font-weight:700;letter-spacing:.13em;text-transform:uppercase;
           color:{B['teal_deep']};margin-bottom:4px;">Secteur &amp; Cara\u00efbe
           <span style="float:right;font-family:monospace;font-weight:400;color:#6E8484;">
           {len(sector)} item{'s' if len(sector) > 1 else ''}</span></div>
      <div style="font-family:monospace;font-size:10px;color:#6E8484;margin-bottom:12px;">
        Hors Martinique. S\u00e9lection plafonn\u00e9e, destinations voisines d'abord.</div>
      <table width="100%" cellpadding="0" cellspacing="0" border="0">{rows}</table>
    </td></tr>"""
    hs = f"{health['queried']} sources interrogées · {health['responded']} réponses · {health['failed']} en échec"
    html = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{CLIENT['digest']['title']} — {week_label}</title></head>
<body style="margin:0;padding:0;background:{B['paper']};">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{B['paper']};padding:24px 12px;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;width:100%;
  background:#FFFFFF;border:1px solid #DBE8E7;border-radius:12px;overflow:hidden;
  font-family:{B['body_font']},Helvetica,Arial,sans-serif;">
  <tr><td style="padding:22px 22px 16px;background:{B['teal_soft']};border-bottom:3px solid {B['teal']};">
    <div style="font-family:{B['display_font']},sans-serif;font-weight:700;font-size:12px;
         letter-spacing:.2em;text-transform:uppercase;color:{B['teal_deep']};">{CLIENT['name']}</div>
    <div style="font-family:{B['display_font']},sans-serif;font-size:32px;font-weight:800;
         line-height:1;margin:6px 0 9px;color:{B['ink']};">{CLIENT['digest']['title']}</div>
    <div style="font-family:monospace;font-size:11px;color:#6E8484;">{week_label} · N° {issue_no:03d}</div>
  </td></tr>
  <tr><td style="padding:12px 22px;background:{B['teal_soft']};font-family:monospace;
       font-size:10.5px;color:{B['teal_deep']};line-height:1.5;">{EDITORIAL['disclosure_fr']}</td></tr>
  {sections}
  <tr><td style="padding:16px 22px 20px;background:#EDF6F5;font-family:monospace;
       font-size:10.5px;color:#6E8484;line-height:1.7;">
    {hs}<br>{EDITORIAL['copyright_note_fr']}<br>
    <a href="%unsubscribe%" style="color:#6E8484;">Se désinscrire</a> ·
    <a href="%archive%" style="color:#6E8484;">Archives</a> ·
    <a href="%contribute%" style="color:#6E8484;">Proposer une actualité</a>
  </td></tr>
</table></td></tr></table></body></html>"""

    lines = [f"{CLIENT['name']} — {CLIENT['digest']['title']} — {week_label}", "", EDITORIAL["disclosure_fr"], ""]
    for t in ORDER:
        for it in by_theme.get(t, []):
            lines += [f"[{LABELS.get(t, t)}] {it.get('headline','')}",
                      f"  {it.get('source','')} · {it.get('versioncreated','')}",
                      f"  {it.get('url','')}", ""]
    if sector:
        lines += ["", "-- Secteur & Cara\u00efbe (hors Martinique) --", ""]
        for it in sector:
            lines += [f"[{LABELS.get(it.get('theme'), it.get('theme'))}] {it.get('headline','')}",
                      f"  {it.get('source','')} \u00b7 {it.get('versioncreated','')}",
                      f"  {it.get('url','')}", ""]
    lines += [hs, EDITORIAL["copyright_note_fr"]]
    txt = "\n".join(lines)

    (OUT_DIR / "digest.html").write_text(html, encoding="utf-8")
    (OUT_DIR / "digest.txt").write_text(txt, encoding="utf-8")
    return html, txt
