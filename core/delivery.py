"""Livraison de l'envoi, avec mode simule.

Deux modes, une seule logique :

  SIMULATE  le message est construit, controle, ecrit en .eml sur disque, et le
            preflight DNS affiche les enregistrements a publier au lieu d'echouer.
            Aucun octet ne sort.
  REEL      le preflight DNS doit passer, sinon l'envoi est refuse.

Le refus est volontaire : un envoi hebdomadaire vers 88 destinataires sans SPF,
DKIM ni DMARC part en indesirable, et le dispositif passe pour casse alors que
la collecte fonctionne. Mieux vaut ne pas envoyer que d'envoyer dans le vide.
"""
import os, socket, subprocess, datetime
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from .config import CLIENT, OUT_DIR

DKIM_SELECTOR = os.environ.get("DKIM_SELECTOR", "vigie")


def simulate():
    return os.environ.get("VIGIE_SIMULATE_DELIVERY", "").strip() in ("1", "true", "yes")


def _txt(name):
    """Interroge le DNS sans dependance externe. Retourne [] si rien ou si dig absent."""
    try:
        out = subprocess.run(["dig", "+short", "TXT", name], capture_output=True,
                             text=True, timeout=8).stdout
        return [l.strip().strip('"') for l in out.splitlines() if l.strip()]
    except Exception:  # noqa: BLE001
        return []


def domain():
    frm = os.environ.get("SMTP_FROM", "")
    if "@" in frm:
        return frm.split("@", 1)[1]
    return CLIENT["website"].split("//")[-1].strip("/").replace("www.", "")


def preflight(dom=None):
    """Controle SPF / DKIM / DMARC. Retourne (ok, rapport)."""
    dom = dom or domain()
    spf = [r for r in _txt(dom) if r.lower().startswith("v=spf1")]
    dmarc = [r for r in _txt("_dmarc." + dom) if r.lower().startswith("v=dmarc1")]
    dkim = [r for r in _txt(f"{DKIM_SELECTOR}._domainkey.{dom}") if "p=" in r]
    checks = [
        {"record": "SPF", "host": dom, "present": bool(spf), "value": spf[0] if spf else None,
         "expected": "v=spf1 include:<votre-routeur-smtp> -all"},
        {"record": "DKIM", "host": f"{DKIM_SELECTOR}._domainkey.{dom}", "present": bool(dkim),
         "value": (dkim[0][:48] + "…") if dkim else None,
         "expected": "v=DKIM1; k=rsa; p=<clé publique fournie par le routeur>"},
        {"record": "DMARC", "host": "_dmarc." + dom, "present": bool(dmarc),
         "value": dmarc[0] if dmarc else None,
         "expected": "v=DMARC1; p=quarantine; rua=mailto:dmarc@" + dom + "; adkim=s; aspf=s"},
    ]
    ok = all(c["present"] for c in checks)
    return ok, {"domain": dom, "checks": checks, "simulated": simulate()}


def print_preflight(rep):
    mark = {True: "OK ", False: "-- "}
    print(f"  domaine : {rep['domain']}")
    for c in rep["checks"]:
        print(f"  [{mark[c['present']]}] {c['record']:<5} {c['host']}")
        if c["present"]:
            print(f"          {c['value']}")
        else:
            print(f"          à publier : {c['expected']}")
    if rep["simulated"] and not all(c["present"] for c in rep["checks"]):
        print("  mode simulé : les enregistrements manquants sont traités comme publiés.")


def build(subject, html, txt, recipients, sender, unsubscribe=None):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = sender
    msg["Bcc"] = ", ".join(recipients)
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=domain())
    mailto = unsubscribe or f"mailto:{sender}?subject=unsubscribe"
    msg["List-Unsubscribe"] = f"<{mailto}>"
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg["List-Id"] = f"{CLIENT['digest']['title']} <{CLIENT['id']}.{domain()}>"
    msg["Auto-Submitted"] = "auto-generated"
    msg.set_content(txt)
    msg.add_alternative(html, subtype="html")
    return msg


def deliver(msg, recipients):
    """Envoie, ou ecrit le .eml si simulation. Retourne (statut, chemin|None)."""
    if simulate():
        stamp = datetime.date.today().isoformat()
        path = OUT_DIR / f"digest_{stamp}.eml"
        path.write_bytes(bytes(msg))
        return "simulé", path
    host = os.environ.get("SMTP_HOST")
    if not host:
        return "SMTP absent", None
    import smtplib
    with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", 587)), timeout=30) as s:
        s.starttls()
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        s.send_message(msg)
    return f"envoyé à {len(recipients)} destinataires", None
