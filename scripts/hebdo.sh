#!/bin/bash
# Run hebdomadaire local. Appele par launchd, ou a la main pour tester.
#
# Pourquoi ce script existe : ni le conteneur d'Anthropic ni la VM du pont
# bureau n'ont d'acces sortant vers les flux de presse (mandataire en 403).
# La seule machine de la chaine qui atteint les sources, c'est ce Mac.
set -u
cd "$(dirname "$0")/.." || exit 1
RACINE="$(pwd)"
JOUR="$(date +%Y-%m-%d)"
JOURNAL="$RACINE/out/logs/vigie-$JOUR.log"
mkdir -p "$RACINE/out/logs"

{
  echo "===== run du $(date '+%F %T') ====="
  if [ ! -x "$RACINE/venv/bin/python" ]; then
    echo "ERREUR : venv introuvable dans $RACINE/venv"; exit 1
  fi
  "$RACINE/venv/bin/python" run.py --cadence weekly
  echo "--- envoi ---"
  VIGIE_SIMULATE_DELIVERY="${VIGIE_SIMULATE_DELIVERY:-1}" \
  SMTP_FROM="${SMTP_FROM:-vigie@zilea-martinique.com}" \
  "$RACINE/venv/bin/python" run.py --send
  echo "===== fin $(date '+%F %T') ====="
} >>"$JOURNAL" 2>&1

# on garde huit semaines de journaux, pas davantage
ls -1t "$RACINE/out/logs"/vigie-*.log 2>/dev/null | tail -n +9 | while read -r f; do mv "$f" "$f.vieux" 2>/dev/null; done
