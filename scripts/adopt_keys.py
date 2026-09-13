#!/usr/bin/env python3
"""Reprend les cles d'un .env existant sans jamais les afficher.

  python scripts/adopt_keys.py ~/chemin/vers/un/.env

Ne copie que les variables attendues par ce dispositif, ignore le reste, et
n'ecrase pas une valeur deja renseignee dans le .env local.
"""
import sys, pathlib, re

WANTED = ["ANTHROPIC_API_KEY", "YOUTUBE_API_KEY", "VIATOR_API_KEY",
          "TRIPADVISOR_API_KEY",
          "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM"]

if len(sys.argv) < 2:
    print(__doc__); sys.exit(1)
src = pathlib.Path(sys.argv[1]).expanduser()
dst = pathlib.Path(__file__).resolve().parent.parent / ".env"
if not src.exists():
    print(f"introuvable : {src}"); sys.exit(1)


def parse(p):
    out = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*([A-Z0-9_]+)\s*=\s*(.*)$", line)
        if m:
            out[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return out


incoming = parse(src)
current = parse(dst) if dst.exists() else {}
taken, skipped, already = [], [], []
for k in WANTED:
    v = incoming.get(k, "")
    if not v:
        skipped.append(k)
    elif current.get(k):
        already.append(k)
    else:
        current[k] = v
        taken.append(k)

lines = [f"{k}={current.get(k, '')}" for k in WANTED]
dst.write_text("\n".join(lines) + "\n", encoding="utf-8")
dst.chmod(0o600)

print(f"source : {src}")
print(f"→ reprises        : {', '.join(taken) if taken else 'aucune'}")
print(f"→ déjà présentes  : {', '.join(already) if already else 'aucune'}")
print(f"→ absentes        : {', '.join(skipped) if skipped else 'aucune'}")
print(f"→ écrit dans {dst} (chmod 600). Aucune valeur n'a été affichée.")
