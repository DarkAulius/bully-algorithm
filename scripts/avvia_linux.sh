#!/usr/bin/env bash
# ============================================================================
#  Avvio dei 5 nodi su Linux: apre 5 finestre di terminale, una per nodo,
#  usando il primo emulatore disponibile (gnome-terminal, konsole, xterm).
#  Dopo l'avvio, nella finestra di P1 digitare  e  e premere Invio per avviare
#  la prima elezione.
#  Uso:  bash scripts/avvia_linux.sh
# ============================================================================
DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR" || exit 1

for i in 5 4 3 2 1; do
  CMD="python3 bully_node.py $i; exec bash"
  if command -v gnome-terminal >/dev/null 2>&1; then
    gnome-terminal --title="P$i - Bully (porta 500$i)" -- bash -c "$CMD"
  elif command -v konsole >/dev/null 2>&1; then
    konsole --new-tab -p tabtitle="P$i" -e bash -c "$CMD" &
  elif command -v xterm >/dev/null 2>&1; then
    xterm -T "P$i - Bully (porta 500$i)" -e bash -c "$CMD" &
  else
    echo "Nessun emulatore di terminale trovato: avviare manualmente"
    echo "  python3 bully_node.py $i   in un terminale separato"
  fi
  sleep 0.3
done
