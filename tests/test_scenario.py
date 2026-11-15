#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verifica automatica dello scenario richiesto dal progetto.

Avvia i 5 nodi come processi separati (su porte 6001..6005 per non
interferire con un'eventuale esecuzione manuale), poi:

  FASE 1  P1 avvia l'elezione (comando "e")  -> atteso coordinatore P5
  FASE 2  P5 viene terminato con SIGINT (lo stesso segnale di Ctrl+C)
  FASE 3  rilevazione del guasto e nuova elezione -> atteso coordinatore P4

e controlla i requisiti di correttezza:
  1. alla fine della prima elezione il coordinatore e' P5 per tutti i nodi
  2. dopo il guasto di P5 l'elezione termina e il coordinatore e' P4
  3. non esistono mai due coordinatori contemporaneamente
  4. l'algoritmo termina (nessuna elezione ancora in corso alla fine)

Uso:  python tests/test_scenario.py
"""

import os
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = os.path.join(ROOT, "bully_node.py")
BASE_PORT = 6000
IDS = [1, 2, 3, 4, 5]


def read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().splitlines()
    except FileNotFoundError:
        return []


def wait_for(predicate, timeout, step=0.1):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(step)
    return predicate()


def ts(line):
    # "[P3] 22:48:01.123  messaggio"  ->  datetime (solo per ordinare gli eventi)
    return datetime.strptime(line.split()[1], "%H:%M:%S.%f")


def main():
    logdir = tempfile.mkdtemp(prefix="bully_test_")
    logs = {i: os.path.join(logdir, "P{}.log".format(i)) for i in IDS}
    procs = {}
    failures = []

    def check(cond, msg):
        print(("  [OK]   " if cond else "  [FAIL] ") + msg)
        if not cond:
            failures.append(msg)

    try:
        # Avvio dei nodi in ordine inverso (P5..P1), ognuno processo separato.
        for i in reversed(IDS):
            procs[i] = subprocess.Popen(
                [sys.executable, NODE, str(i), "--porta-base", str(BASE_PORT),
                 "--no-colori", "--log-file", logs[i]],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
                text=True)
        ok = wait_for(lambda: all(any("Nodo attivo" in l for l in read(logs[i])) for i in IDS), 10)
        check(ok, "i 5 nodi sono attivi su porte {}..{}".format(BASE_PORT + 1, BASE_PORT + 5))
        time.sleep(1.0)

        # ---------------- FASE 1: prima elezione avviata da P1 ----------------
        print("\nFASE 1 - P1 avvia l'elezione")
        procs[1].stdin.write("e\n")
        procs[1].stdin.flush()
        ok = wait_for(lambda: all(any("Coordinatore registrato: P5" in l for l in read(logs[i]))
                                  for i in [1, 2, 3, 4]), 15)
        check(ok, "P1..P4 registrano P5 come coordinatore")
        check(any("Mi dichiaro COORDINATORE" in l for l in read(logs[5])),
              "P5 si dichiara coordinatore tramite l'algoritmo")
        check(not any("Mi dichiaro COORDINATORE" in l for i in [1, 2, 3, 4] for l in read(logs[i])),
              "nessun altro nodo si dichiara coordinatore nella fase 1")
        time.sleep(4.0)   # stato stabile: i nodi verificano periodicamente P5

        # ---------------- FASE 2: guasto del coordinatore P5 ----------------
        print("\nFASE 2 - P5 terminato con SIGINT (Ctrl+C)")
        if os.name == "nt":
            procs[5].terminate()
        else:
            procs[5].send_signal(signal.SIGINT)
        procs[5].wait(timeout=5)
        check(any("processo terminato" in l for l in read(logs[5])) or os.name == "nt",
              "P5 terminato")
        kill_time = datetime.now()

        # ---------------- FASE 3: nuova elezione ----------------
        print("\nFASE 3 - rilevazione del guasto e nuova elezione")
        ok = wait_for(lambda: all(any("Coordinatore registrato: P4" in l for l in read(logs[i]))
                                  for i in [1, 2, 3]), 25)
        check(ok, "P1..P3 registrano P4 come nuovo coordinatore")
        check(any("TIMEOUT: il coordinatore P5 non risponde" in l
                  for i in [1, 2, 3, 4] for l in read(logs[i])),
              "almeno un nodo rileva il guasto di P5 per timeout")
        check(any("TIMEOUT T" in l and "P5" in l for l in read(logs[4])),
              "P4 non riceve risposta da P5 entro T")
        time.sleep(4.0)

        # Requisito 4: terminazione -> chiedo lo stato a P1..P4.
        for i in [1, 2, 3, 4]:
            procs[i].stdin.write("s\n")
            procs[i].stdin.flush()
        time.sleep(1.0)
        for i in [1, 2, 3, 4]:
            last = [l for l in read(logs[i]) if "Stato:" in l]
            check(bool(last) and "coordinatore = P4, elezione in corso = no" in last[-1],
                  "P{} stato finale: coordinatore P4, nessuna elezione in corso".format(i))

        # Requisito 3: mai due coordinatori contemporaneamente.
        declarations = [(ts(l), i) for i in IDS for l in read(logs[i])
                        if "Mi dichiaro COORDINATORE" in l]
        p5_end = [ts(l) for l in read(logs[5]) if "processo terminato" in l]
        p4_decl = [t for t, i in declarations if i == 4]
        check(set(i for _, i in declarations) <= {4, 5},
              "solo P5 e P4 si sono mai dichiarati coordinatore")
        check(bool(p4_decl) and bool(p5_end) and min(p4_decl) > p5_end[0],
              "P4 si dichiara coordinatore solo DOPO la terminazione di P5")
    finally:
        for p in procs.values():
            if p.poll() is None:
                p.terminate()
        for p in procs.values():
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()

    print("\nLog completi in: {}".format(logdir))
    if failures:
        print("\nRISULTATO: {} controlli FALLITI".format(len(failures)))
        sys.exit(1)
    print("\nRISULTATO: tutti i controlli superati")


if __name__ == "__main__":
    main()
