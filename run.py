#!/usr/bin/env python3
"""Orchestrateur.

  python run.py --cadence weekly            collecte + classement + resume + rendu
  python run.py --cadence daily             alertes seulement
  python run.py --cadence weekly --dry-run  aucun appel au modele
  python run.py --render-only               regenere le radar depuis le corpus
  python run.py --send                      envoie le digest (SMTP)

Chaque run ecrit des releves horodates. Un compteur non releve est perdu :
les ecarts n'existent que si on a commence a stocker tot.
"""
import argparse, datetime, os, sys, json
from dotenv import load_dotenv

load_dotenv()

from core import store, editorial, llm, health           # noqa: E402
from core.config import CLIENT, OUT_DIR                  # noqa: E402
from render import radar, digest, sources as sources_page  # noqa: E402


def week_label(d=None):
    d = d or datetime.date.today()
    iso = d.isocalendar()
    start = datetime.date.fromisocalendar(iso[0], iso[1], 1)
    end = start + datetime.timedelta(days=6)
    return f"Semaine {iso[1]} · {start.strftime('%d/%m')} → {end.strftime('%d/%m/%Y')}"


def run(cadence, dry_run=False):
    # imports tardifs : --render-only et --preflight ne doivent pas exiger
    # les dependances de collecte
    from collectors import press, youtube, offers, alerts, tripadvisor
    checks, new_items, snaps = [], [], []
    log = lambda m: print(f"  {m}", flush=True)  # noqa: E731

    def step(label, fn, fmt):
        """Un collecteur qui tombe ne doit pas emporter les autres.

        La collecte est la partie la plus fragile du dispositif : elle depend
        d'une trentaine de sites tiers dont le HTML change sans preavis. Perdre
        700 articles parce qu'un compteur de marketplace est illisible serait
        un mauvais arbitrage. L'echec est trace en sante, le run continue.
        """
        print(f"→ {label}")
        try:
            res = fn()
        except Exception as e:  # noqa: BLE001
            log(f"échec : {type(e).__name__} — {e}")
            return [], [], [{"source": label, "ok": False, "error": type(e).__name__}]
        got = res[0]
        sn = res[1] if len(res) == 3 else []
        h = res[-1]
        log(fmt(got, sn))
        return got, sn, h

    if cadence in ("daily", "all"):
        g, s, h = step("alertes", alerts.collect, lambda g, s: f"{len(g)} alerte(s)")
        new_items += g; snaps += s; checks += h

    if cadence in ("weekly", "all"):
        g, s, h = step("presse", lambda: press.collect("weekly"),
                       lambda g, s: f"{len(g)} items bruts")
        new_items += g; snaps += s; checks += h

        g, s, h = step("vidéos", youtube.collect,
                       lambda g, s: f"{len(g)} vidéos, {len(s)} relevés")
        new_items += g; snaps += s; checks += h

        g, s, h = step("offre", offers.collect,
                       lambda g, s: f"{len(g)} activités, {len(s)} relevés")
        new_items += g; snaps += s; checks += h

    # le theme est attribue AVANT l'ecriture, sinon l'enrichissement ne survit
    # pas au run : le radar relit corpus.jsonl, pas la memoire du processus
    for it in new_items:
        llm.classify(it, dry_run=dry_run)

    fresh = store.append_items(new_items)
    print(f"→ corpus : {len(fresh)} nouveaux items sur {len(new_items)} collectés")
    if snaps:
        store.append_snapshots(snaps)
        print(f"→ relevés : {len(snaps)} compteurs horodatés")

    # tout ce qui entre au corpus n'a pas vocation a partir dans l'envoi :
    # les videos alimentent le radar, pas la revue de presse
    retenus, secteur, ecartes = editorial.eligible(fresh)
    avant = len(retenus) + len(secteur)
    retenus, secteur = editorial.dedupe(retenus), editorial.dedupe(secteur)
    if avant != len(retenus) + len(secteur):
        print(f"\u2192 doublons : {avant - len(retenus) - len(secteur)} reprises fusionn\u00e9es")
    print(f"→ éligibles : {len(retenus)} sur {len(fresh)} "
          f"(hors type {ecartes['hors_type']} · hors fenêtre {ecartes['hors_fenetre']} · "
          f"hors sujet {ecartes['hors_sujet']})")

    buckets = editorial.split(retenus)
    print(f"→ routage : {len(buckets['members'])} adhérents · "
          f"{len(buckets['president'])} président · {len(buckets['exclude'])} exclus")

    # les liens Google News ne sont resolus que sur ce qui part dans l'envoi :
    # une vingtaine d'appels, pas les trois cents collectes
    from core import normalize
    n = normalize.resolve_all(buckets["members"] + buckets["president"])
    if n:
        print(f"\u2192 liens : {n} redirection(s) Google News r\u00e9solue(s)")

    for it in buckets["members"]:
        llm.summarize(it, dry_run=dry_run)

    hs = health.summarize(checks)
    arb = health.to_arbitrate(checks)
    health.record(checks)
    print(f"→ santé : {hs['responded']}/{hs['queried']} sources")
    if hs["failed_names"]:
        print(f"  en échec : {', '.join(hs['failed_names'][:8])}")
    if arb:
        (OUT_DIR / "a_arbitrer.json").write_text(
            json.dumps(arb, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"→ {len(arb)} point(s) à arbitrer")

    # le digest president se rend EN PREMIER : digest.render ecrit toujours sous
    # digest.html, et le renommage qui suit emporterait la revue des adherents
    if buckets["president"]:
        digest.render(buckets["president"], hs, week_label() + " · réservé au président")
        os.replace(OUT_DIR / "digest.html", OUT_DIR / "digest_president.html")
        os.replace(OUT_DIR / "digest.txt", OUT_DIR / "digest_president.txt")
        print(f"→ envoi président : {len(buckets['president'])} item(s)")

    if editorial.should_send(len(buckets["members"])):
        digest.render(buckets["members"], hs, week_label(), sector=secteur)
        print(f"→ digest généré : {OUT_DIR/'digest.html'}")
    else:
        print(f"→ plancher non atteint ({len(buckets['members'])} items) : pas d'envoi cette semaine")

    out, payload = radar.render()
    print(f"→ radar régénéré : {out}")

    # Le site publie sert out/ tel quel. Ces deux pages n'etaient produites
    # qu'a la main : la racine partagee renvoyait une 404 et l'inventaire des
    # sources ne quittait jamais le poste.
    print(f"→ sources et page d'accueil : {sources_page.render()}")
    return 0


def send():
    """Envoi reel ou simule. Le preflight DNS decide."""
    from core import delivery
    ok, rep = delivery.preflight()
    print("→ préflight délivrabilité")
    delivery.print_preflight(rep)
    if not ok and not delivery.simulate():
        print("→ envoi refusé : SPF, DKIM et DMARC doivent être publiés.")
        print("  Pour répéter sans DNS : VIGIE_SIMULATE_DELIVERY=1")
        return 1
    html_p, txt_p = OUT_DIR / "digest.html", OUT_DIR / "digest.txt"
    if not html_p.exists():
        print("→ aucun digest généré (plancher non atteint ?)"); return 1
    rec_file = CLIENT["digest"]["recipients_file"]
    rec = []
    if os.path.exists(rec_file):
        rec = [l.strip() for l in open(rec_file, encoding="utf-8")
               if l.strip() and not l.startswith("#")]
    if not rec:
        rec = ["destinataire-test@" + delivery.domain()]
        print(f"→ liste vide, destinataire de répétition : {rec[0]}")
    sender = os.environ.get("SMTP_FROM") or ("vigie@" + delivery.domain())
    msg = delivery.build(
        f"{CLIENT['digest']['title']} — {week_label()}",
        html_p.read_text(encoding="utf-8"), txt_p.read_text(encoding="utf-8"),
        rec, sender)
    status, path = delivery.deliver(msg, rec)
    print(f"→ {status}" + (f" : {path}" if path else ""))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cadence", default="weekly", choices=["daily", "weekly", "all"])
    ap.add_argument("--dry-run", action="store_true", help="aucun appel au modèle")
    ap.add_argument("--render-only", action="store_true")
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--preflight", action="store_true", help="contrôle DNS seulement")
    a = ap.parse_args()
    if a.preflight:
        from core import delivery
        ok, rep = delivery.preflight(); delivery.print_preflight(rep)
        sys.exit(0 if (ok or delivery.simulate()) else 1)
    if a.send:
        sys.exit(send())
    if a.render_only:
        out, _ = radar.render(); print(f"→ {out}"); sys.exit(0)
    sys.exit(run(a.cadence, a.dry_run))
