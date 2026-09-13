#!/usr/bin/env python3
"""Controle autonome des enregistrements de deliverabilite.

  python scripts/dns_preflight.py                 domaine deduit de SMTP_FROM
  python scripts/dns_preflight.py exemple.com     domaine explicite
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv()
from core import delivery

dom = sys.argv[1] if len(sys.argv) > 1 else None
ok, rep = delivery.preflight(dom)
print("Préflight délivrabilité")
delivery.print_preflight(rep)
print()
if ok:
    print("→ prêt pour un envoi réel.")
elif rep["simulated"]:
    print("→ mode simulé actif : l'envoi produira un .eml sur disque, rien ne sortira.")
else:
    print("→ envoi réel refusé tant que les trois enregistrements ne sont pas publiés.")
    print("  Pour répéter sans DNS : VIGIE_SIMULATE_DELIVERY=1")
sys.exit(0 if (ok or rep["simulated"]) else 1)
