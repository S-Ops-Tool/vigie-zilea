#!/usr/bin/env python3
"""Reproduit l'echec de resume et affiche la trace complete.

La chaine "echec resume (TypeError)" ne dit que le nom de l'erreur. Le motif
est dans la trace, que le collecteur avale volontairement pour ne jamais
interrompre une collecte. Ce script refait le meme appel, seul, et laisse tout
remonter.

Un appel au modele, quelques centimes.
"""
import sys
import pathlib
import traceback

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from core import llm                       # noqa: E402
from core.config import EDITORIAL          # noqa: E402

print("--- environnement ---")
print("python    :", sys.version.split()[0])
for mod in ("anthropic", "httpx", "httpcore", "pydantic", "anyio"):
    try:
        m = __import__(mod)
        print(f"{mod:10}:", getattr(m, "__version__", "?"))
    except Exception as e:                   # noqa: BLE001
        print(f"{mod:10}: absent ({type(e).__name__})")

cfg = EDITORIAL["summary"]
print("\n--- parametres ---")
print("model      :", repr(cfg.get("model")))
print("max_tokens :", 300)
print("system     :", type(llm.SYSTEM).__name__, len(llm.SYSTEM))

print("\n--- construction du client ---")
try:
    cli = llm._client()
    print("client :", type(cli).__name__ if cli else "None (pas de cle)")
except Exception:                            # noqa: BLE001
    print("ECHEC a la construction du client :")
    traceback.print_exc()
    sys.exit(1)

if cli is None:
    print("ANTHROPIC_API_KEY absente du .env")
    sys.exit(1)

print("\n--- appel ---")
try:
    r = cli.messages.create(
        model=cfg["model"],
        max_tokens=300,
        system=llm.SYSTEM,
        messages=[{"role": "user", "content":
                   "Titre : Frequentation hoteliere en hausse\n\nTexte :\n"
                   "Les hotels de Martinique annoncent une frequentation en "
                   "progression sur le premier semestre, portee par la clientele "
                   "hexagonale. Les professionnels restent prudents sur la suite "
                   "de la saison, en raison des incertitudes sur la desserte "
                   "aerienne et du retour annonce des sargasses."}],
    )
    print("REUSSITE :", r.content[0].text[:160])
except Exception as e:                       # noqa: BLE001
    print("ECHEC :", type(e).__name__)
    print("message :", str(e)[:400])
    print("\n--- trace complete ---")
    traceback.print_exc()
