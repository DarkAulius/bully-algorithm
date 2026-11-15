#!/usr/bin/env bash
# ============================================================================
#  Alternativa per Linux/macOS con tmux: una sessione con 5 riquadri, ognuno
#  e' un terminale separato con il proprio nodo (P1..P5).
#  Navigazione tra i riquadri: Ctrl+b e poi le frecce.
#  Uso:  bash scripts/avvia_tmux.sh
# ============================================================================
DIR="$(cd "$(dirname "$0")/.." && pwd)"
SESSION=bully

tmux kill-session -t "$SESSION" 2>/dev/null
tmux new-session -d -s "$SESSION" -c "$DIR" "python3 bully_node.py 1; exec bash"
for i in 2 3 4 5; do
  tmux split-window -t "$SESSION" -c "$DIR" "python3 bully_node.py $i; exec bash"
  tmux select-layout -t "$SESSION" tiled >/dev/null
done
tmux set -t "$SESSION" pane-border-status top
tmux set -t "$SESSION" pane-border-format " #{pane_index}: #{pane_title} "
tmux select-pane -t "$SESSION".0
tmux attach -t "$SESSION"
