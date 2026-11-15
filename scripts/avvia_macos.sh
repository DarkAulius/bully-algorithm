#!/usr/bin/env bash
# ============================================================================
#  Avvio dei 5 nodi su macOS: apre 5 finestre dell'app Terminale, una per nodo.
#  Dopo l'avvio, nella finestra di P1 digitare  e  e premere Invio per avviare
#  la prima elezione.
#  Uso:  bash scripts/avvia_macos.sh
# ============================================================================
DIR="$(cd "$(dirname "$0")/.." && pwd)"
for i in 5 4 3 2 1; do
  osascript -e "tell application \"Terminal\" to do script \"cd '$DIR' && python3 bully_node.py $i\""
done
osascript -e 'tell application "Terminal" to activate'
