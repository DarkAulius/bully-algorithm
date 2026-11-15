#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 ELEZIONE DEL COORDINATORE CON L'ALGORITMO DEL BULLO (BULLY ALGORITHM)
===============================================================================

Ogni esecuzione di questo file e' UN nodo indipendente del sistema distribuito.
Il sistema e' composto da 5 nodi (P1..P5), ognuno avviato in un terminale
separato:

    python bully_node.py 1      ->  nodo P1, in ascolto su 127.0.0.1:5001
    python bully_node.py 2      ->  nodo P2, in ascolto su 127.0.0.1:5002
    python bully_node.py 3      ->  nodo P3, in ascolto su 127.0.0.1:5003
    python bully_node.py 4      ->  nodo P4, in ascolto su 127.0.0.1:5004
    python bully_node.py 5      ->  nodo P5, in ascolto su 127.0.0.1:5005

Principi di progetto
--------------------
* Nessuna memoria condivisa: ogni nodo e' un processo separato con il proprio
  stato privato (coordinatore noto, elezione in corso, ...).
* Comunicazione SOLO tramite messaggi su socket TCP in localhost.
* Sono implementati SOLO i tre messaggi dell'algoritmo:
      ELECTION     "voglio diventare coordinatore": inviato ai nodi con ID maggiore
      ANSWER       "ci sono io, che ho ID maggiore": risposta a ELECTION
      COORDINATOR  "sono il nuovo coordinatore": inviato ai nodi con ID minore
* Nessun coordinatore predefinito: all'avvio nessun nodo conosce il
  coordinatore; P5 lo diventa solo come risultato della prima elezione.
* Timeout reali (misurati con l'orologio monotono del sistema operativo):
      T   tempo massimo di attesa delle ANSWER dopo aver inviato ELECTION.
          E' usato anche come finestra massima entro cui un nodo deve riuscire
          a contattare il coordinatore: se non ci riesce, il coordinatore e'
          considerato guasto.
      T'  tempo massimo di attesa del messaggio COORDINATOR dopo aver
          ricevuto almeno una ANSWER. Se scade, l'elezione viene riavviata
          (garantisce la terminazione anche se il nodo "piu' forte" si guasta
          durante l'elezione).

Formato dei messaggi sulla rete
-------------------------------
Una connessione TCP per messaggio; il contenuto e' una riga JSON:

    {"type": "ELECTION", "from": 3}\n

Solo libreria standard di Python (>= 3.8): nessuna dipendenza esterna.
===============================================================================
"""

import argparse
import json
import os
import random
import signal
import socket
import sys
import threading
import time
from datetime import datetime

# -----------------------------------------------------------------------------
# Configurazione statica del sistema
# -----------------------------------------------------------------------------
ALL_IDS = [1, 2, 3, 4, 5]          # i 5 nodi del sistema (P1..P5)
DEFAULT_HOST = "127.0.0.1"         # tutti i nodi girano su localhost
DEFAULT_BASE_PORT = 5000           # porta del nodo Pi = DEFAULT_BASE_PORT + i

DEFAULT_T = 2.0                    # T : attesa massima delle ANSWER (secondi)
DEFAULT_T_PRIME = 6.0              # T': attesa massima del COORDINATOR (secondi)
DEFAULT_CHECK_INTERVAL = 2.0       # ogni quanto si verifica il coordinatore

# Tipi di messaggio: gli UNICI scambiati dai nodi.
ELECTION = "ELECTION"
ANSWER = "ANSWER"
COORDINATOR = "COORDINATOR"
VALID_MESSAGES = (ELECTION, ANSWER, COORDINATOR)


# -----------------------------------------------------------------------------
# Colori ANSI per rendere i log leggibili (disattivabili con --no-colori)
# -----------------------------------------------------------------------------
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"


# Colore distintivo dell'etichetta [Pi] di ciascun nodo.
NODE_COLORS = {1: Colors.CYAN, 2: Colors.BLUE, 3: Colors.MAGENTA,
               4: Colors.YELLOW, 5: Colors.GREEN}

# Colore di ogni tipo di evento.
EVENT_COLORS = {
    ELECTION: Colors.YELLOW,
    ANSWER: Colors.CYAN,
    COORDINATOR: Colors.GREEN,
    "TIMEOUT": Colors.RED + Colors.BOLD,
    "ERROR": Colors.RED,
    "LEADER": Colors.GREEN + Colors.BOLD,
    "START": Colors.MAGENTA + Colors.BOLD,
    "INFO": "",
    "DIM": Colors.DIM,
}


class BullyNode:
    """Un nodo (processo) che partecipa all'elezione con l'Algoritmo del Bullo."""

    def __init__(self, node_id, host, base_port, t_answer, t_coordinator,
                 check_interval, use_colors, log_file=None):
        self.id = node_id
        self.host = host
        self.base_port = base_port
        self.port = base_port + node_id
        self.T = t_answer              # timeout T  (attesa ANSWER)
        self.T_PRIME = t_coordinator   # timeout T' (attesa COORDINATOR)
        self.check_interval = check_interval
        self.use_colors = use_colors

        # ---------------------------------------------------------------
        # STATO PRIVATO DEL NODO (nessuna memoria condivisa con gli altri)
        # Protetto da un'unica Condition: i thread del nodo (server, elezione,
        # monitor del coordinatore, comandi da tastiera) lo leggono e scrivono
        # sempre sotto questo lock.
        # ---------------------------------------------------------------
        self.cv = threading.Condition()
        self.coordinator = None          # ID del coordinatore noto (None = sconosciuto)
        self.election_active = False     # True mentre questo nodo conduce un'elezione
        self.answer_received = False     # ricevuta almeno una ANSWER nell'elezione corrente
        # Numero di "turno" dell'elezione: viene incrementato quando un'elezione
        # inizia, termina o viene arrestata da un COORDINATOR. Le attese con
        # timeout confrontano il proprio turno con quello corrente: se e'
        # cambiato, l'elezione che stavano servendo non e' piu' valida.
        self.election_round = 0

        self.stop_event = threading.Event()
        self.print_lock = threading.Lock()
        self.server_socket = None
        self.log_file = None
        if log_file:
            os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
            self.log_file = open(log_file, "a", encoding="utf-8", buffering=1)

    # =========================================================================
    # LOG
    # =========================================================================
    def log(self, message, kind="INFO"):
        """Stampa una riga di log con identificativo del nodo e orario (ms)."""
        with self.print_lock:   # orario preso sotto lock: righe sempre in ordine
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            plain = "[P{}] {}  {}".format(self.id, timestamp, message)
            if self.use_colors:
                tag = "{}{}[P{}]{}".format(Colors.BOLD, NODE_COLORS[self.id], self.id,
                                           Colors.RESET)
                color = EVENT_COLORS.get(kind, "")
                line = "{} {}{}{}  {}{}{}".format(tag, Colors.DIM, timestamp, Colors.RESET,
                                                  color, message, Colors.RESET)
            else:
                line = plain
            print(line, flush=True)
            if self.log_file:
                self.log_file.write(plain + "\n")

    def address_of(self, node_id):
        """Indirizzo (host, porta) del nodo node_id su localhost."""
        return (self.host, self.base_port + node_id)

    # =========================================================================
    # SCAMBIO DI MESSAGGI - INVIO
    # =========================================================================
    def send(self, dest_id, msg_type):
        """
        Invia il messaggio msg_type (ELECTION / ANSWER / COORDINATOR) al nodo
        dest_id aprendo una connessione TCP verso la sua porta su localhost.

        Se il destinatario e' terminato (es. P5 dopo Ctrl+C) la connessione
        fallisce: il messaggio NON viene consegnato e lo si registra nel log.
        La decisione su un nodo che non risponde NON viene presa qui, ma solo
        alla scadenza dei timeout T / T' (vedi run_election).
        """
        payload = (json.dumps({"type": msg_type, "from": self.id}) + "\n").encode("utf-8")
        try:
            # Timeout di connessione breve: su localhost un nodo attivo accetta
            # subito; un nodo terminato rifiuta (o non risponde) la connessione.
            with socket.create_connection(self.address_of(dest_id), timeout=0.5) as s:
                s.sendall(payload)
            self.log("--> {} inviato a P{}".format(msg_type, dest_id), msg_type)
            return True
        except OSError:
            self.log("--> {} a P{} NON consegnato: nodo irraggiungibile".format(msg_type, dest_id),
                     "ERROR")
            return False

    # =========================================================================
    # SCAMBIO DI MESSAGGI - RICEZIONE (server TCP del nodo)
    # =========================================================================
    def start_server(self):
        """Apre la porta del nodo su localhost e avvia il thread di ricezione."""
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if os.name != "nt":
            # Su Linux/macOS permette di riavviare subito un nodo sulla stessa porta.
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen(16)
        srv.settimeout(0.5)   # per poter controllare periodicamente stop_event
        self.server_socket = srv
        threading.Thread(target=self._accept_loop, name="server", daemon=True).start()

    def _accept_loop(self):
        while not self.stop_event.is_set():
            try:
                conn, _ = self.server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break  # socket chiuso durante la terminazione
            # Ogni connessione e' gestita in un thread dedicato, cosi' il server
            # resta sempre pronto a ricevere (es. ANSWER mentre si attende T).
            threading.Thread(target=self._handle_connection, args=(conn,), daemon=True).start()

    def _handle_connection(self, conn):
        """Legge un messaggio (una riga JSON) e lo smista al gestore corretto."""
        data = b""
        try:
            with conn:
                conn.settimeout(2.0)
                while not data.endswith(b"\n") and len(data) < 4096:
                    chunk = conn.recv(1024)
                    if not chunk:
                        break
                    data += chunk
        except OSError:
            return
        if not data.strip():
            # Connessione senza contenuto: e' il semplice tentativo di contatto
            # usato dagli altri nodi per verificare che questo nodo (se
            # coordinatore) sia ancora attivo. Non e' un messaggio applicativo.
            return
        try:
            message = json.loads(data.decode("utf-8"))
            msg_type = message["type"]
            sender = int(message["from"])
        except (ValueError, KeyError, TypeError):
            self.log("Messaggio non valido ignorato: {!r}".format(data[:80]), "ERROR")
            return
        if msg_type not in VALID_MESSAGES or sender not in ALL_IDS:
            self.log("Messaggio sconosciuto ignorato: {!r}".format(message), "ERROR")
            return

        if msg_type == ELECTION:
            self.on_election(sender)
        elif msg_type == ANSWER:
            self.on_answer(sender)
        elif msg_type == COORDINATOR:
            self.on_coordinator(sender)

    # =========================================================================
    # GESTORE DEL MESSAGGIO ELECTION
    # =========================================================================
    def on_election(self, sender):
        """
        Ricevuto ELECTION da un nodo con ID inferiore:
          1. rispondo ANSWER (cosi' il mittente sa che esiste un nodo piu'
             "forte" attivo e si ritira dall'elezione);
          2. avvio una MIA elezione, se non ne ho gia' una in corso
             (e' il meccanismo del "bullo": il nodo piu' forte prende il
             controllo dell'elezione).
        Caso particolare: se sono gia' il coordinatore in carica, invece di
        rifare un'elezione che vincerei comunque, confermo il mio ruolo al
        mittente inviandogli COORDINATOR.
        """
        if sender >= self.id:
            self.log("<-- ELECTION ricevuto da P{} (ignorato)".format(sender), ELECTION)
            return  # per costruzione ELECTION arriva solo da ID inferiori

        # La decisione "avvio la mia elezione?" viene presa in modo atomico
        # NEL MOMENTO della ricezione, prima di qualunque operazione lenta
        # (stampa, invio di ANSWER): cosi' un ELECTION arrivato durante la mia
        # elezione non ne fa partire una seconda subito dopo.
        with self.cv:
            i_am_coordinator = (self.coordinator == self.id)
            my_round = None if i_am_coordinator else self._begin_election()

        self.log("<-- ELECTION ricevuto da P{}".format(sender), ELECTION)
        self.send(sender, ANSWER)
        if i_am_coordinator:
            self.log("Sono il coordinatore in carica: lo confermo a P{}".format(sender), "LEADER")
            self.send(sender, COORDINATOR)
        elif my_round is None:
            self.log("Elezione gia' in corso: non ne avvio un'altra", "DIM")
        else:
            self._launch_election(my_round, "ricevuto ELECTION da P{}".format(sender))

    # =========================================================================
    # GESTORE DEL MESSAGGIO ANSWER
    # =========================================================================
    def on_answer(self, sender):
        """
        Ricevuto ANSWER da un nodo con ID superiore: esiste un nodo piu' forte
        attivo, quindi questo nodo NON si proclamera' coordinatore. Sveglia il
        thread dell'elezione, che smette di attendere T e passa ad attendere
        il COORDINATOR (timeout T').
        """
        with self.cv:
            active = self.election_active
            if active:
                self.answer_received = True
                self.cv.notify_all()
        if active:
            self.log("<-- ANSWER ricevuto da P{}: mi ritiro dall'elezione".format(sender), ANSWER)
        else:
            self.log("<-- ANSWER ricevuto da P{} (nessuna elezione in corso)".format(sender), ANSWER)

    # =========================================================================
    # GESTORE DEL MESSAGGIO COORDINATOR
    # (arresta l'eventuale elezione in corso)
    # =========================================================================
    def on_coordinator(self, sender):
        """
        Ricevuto COORDINATOR: il mittente si e' proclamato coordinatore.
          * Registro il nuovo coordinatore.
          * ARRESTO l'elezione eventualmente in corso: incrementando
            election_round, le attese T / T' del thread dell'elezione si
            accorgono che il loro turno non e' piu' valido e terminano
            senza proclamare nulla. Questo garantisce che non si formino
            due coordinatori.
        Se il mittente ha ID INFERIORE al mio, non lo accetto: indico
        un'elezione per riprendermi il ruolo (regola del bullo).
        """
        if sender < self.id:
            self.log("<-- COORDINATOR da P{}, ma il mio ID e' maggiore".format(sender), COORDINATOR)
            self.start_election("COORDINATOR da un nodo con ID inferiore")
            return

        with self.cv:
            was_electing = self.election_active
            was_coordinator = (self.coordinator == self.id)
            self.coordinator = sender
            self.election_active = False
            self.election_round += 1      # invalida le attese dell'elezione in corso
            self.cv.notify_all()

        self.log("<-- COORDINATOR ricevuto da P{}".format(sender), COORDINATOR)
        if was_electing:
            self.log("Elezione in corso ARRESTATA (ricevuto COORDINATOR)", "INFO")
        if was_coordinator:
            self.log("Non sono piu' il coordinatore", "INFO")
        self.log("Coordinatore registrato: P{}  -> stato stabile".format(sender), "LEADER")

    # =========================================================================
    # AVVIO DELL'ELEZIONE
    # =========================================================================
    def start_election(self, reason):
        """
        Avvia un'elezione, a meno che questo nodo non ne stia gia' conducendo
        una (in quel caso non serve avviarne un'altra). L'elezione vera e
        propria gira in un thread separato perche' contiene attese (T, T').
        """
        with self.cv:
            my_round = self._begin_election()
        if my_round is None:
            self.log("Elezione gia' in corso: non ne avvio un'altra", "DIM")
            return
        self._launch_election(my_round, reason)

    def _begin_election(self):
        """Segna l'inizio di una nuova elezione nello stato del nodo.
        Va chiamata con self.cv acquisito. Ritorna il numero di turno della
        nuova elezione, oppure None se un'elezione e' gia' in corso."""
        if self.election_active:
            return None
        self.election_active = True
        self.answer_received = False
        self.coordinator = None          # durante l'elezione il coordinatore e' ignoto
        self.election_round += 1
        return self.election_round

    def _launch_election(self, my_round, reason):
        threading.Thread(target=self.run_election, args=(my_round, reason),
                         name="elezione", daemon=True).start()

    def run_election(self, my_round, reason):
        """Corpo dell'elezione secondo l'Algoritmo del Bullo."""
        self.log("*** AVVIO ELEZIONE *** ({})".format(reason), "START")

        higher = [n for n in ALL_IDS if n > self.id]
        if not higher:
            # Sono il nodo con ID massimo: nessuno puo' rispondermi ANSWER.
            self.log("Nessun nodo con ID superiore", "INFO")
            self.become_coordinator(my_round)
            return

        # 1) Invio ELECTION a TUTTI i nodi con ID piu' alto (anche a quelli
        #    che potrebbero essere guasti: lo stabilira' il timeout T).
        for n in higher:
            self.send(n, ELECTION)

        # 2) TIMEOUT T: attendo una ANSWER per al massimo T secondi.
        #    Attesa reale sulla Condition, svegliata da on_answer() oppure da
        #    on_coordinator() (che cambia election_round).
        self.log("Attendo ANSWER per al massimo T = {:.1f}s".format(self.T), "DIM")
        deadline = time.monotonic() + self.T
        with self.cv:
            while (not self.answer_received and self.election_round == my_round
                   and not self.stop_event.is_set()):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self.cv.wait(remaining)
            if self.election_round != my_round or self.stop_event.is_set():
                return  # elezione arrestata da un COORDINATOR ricevuto nel frattempo
            got_answer = self.answer_received

        if not got_answer:
            # Nessun nodo con ID superiore ha risposto entro T: sono il nodo
            # attivo con ID piu' alto -> mi proclamo coordinatore.
            missing = ", ".join("P{}".format(n) for n in higher)
            self.log("TIMEOUT T ({:.1f}s) scaduto: nessuna risposta da {}".format(self.T, missing),
                     "TIMEOUT")
            self.become_coordinator(my_round)
            return

        # 3) TIMEOUT T': ho ricevuto ANSWER, quindi un nodo piu' forte sta
        #    conducendo l'elezione. Attendo il suo COORDINATOR per al massimo T'.
        self.log("Attendo COORDINATOR per al massimo T' = {:.1f}s".format(self.T_PRIME), "DIM")
        deadline = time.monotonic() + self.T_PRIME
        with self.cv:
            while self.election_round == my_round and not self.stop_event.is_set():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self.cv.wait(remaining)
            if self.election_round != my_round or self.stop_event.is_set():
                return  # COORDINATOR ricevuto: elezione conclusa correttamente
            # T' scaduto senza COORDINATOR: il nodo che aveva risposto si e'
            # probabilmente guastato durante l'elezione -> riavvio l'elezione.
            self.election_active = False
        self.log("TIMEOUT T' ({:.1f}s) scaduto: nessun COORDINATOR ricevuto".format(self.T_PRIME),
                 "TIMEOUT")
        self.start_election("timeout T' scaduto")

    # =========================================================================
    # PROCLAMAZIONE DEL COORDINATORE
    # =========================================================================
    def become_coordinator(self, my_round):
        """Il nodo si proclama coordinatore e lo comunica ai nodi con ID inferiore."""
        with self.cv:
            if self.election_round != my_round:
                return  # nel frattempo e' arrivato un COORDINATOR: elezione superata
            self.coordinator = self.id
            self.election_active = False
            self.election_round += 1
            self.cv.notify_all()

        self.log("*** Mi dichiaro COORDINATORE ***", "LEADER")
        for n in sorted((n for n in ALL_IDS if n < self.id), reverse=True):
            self.send(n, COORDINATOR)
        self.log("Sistema in stato stabile: coordinatore = P{}".format(self.id), "LEADER")

    # =========================================================================
    # RILEVAZIONE DEL GUASTO DEL COORDINATORE (es. P5 terminato con Ctrl+C)
    # =========================================================================
    def monitor_coordinator(self):
        """
        Thread che, a intervalli regolari, tenta di comunicare con il
        coordinatore. Il tentativo consiste nell'aprire una connessione TCP
        verso la sua porta (senza inviare messaggi applicativi: gli unici
        messaggi del protocollo restano ELECTION/ANSWER/COORDINATOR).
        Se entro il timeout T il coordinatore non risulta raggiungibile,
        e' considerato GUASTO e il nodo avvia una nuova elezione.
        """
        # Piccolo sfasamento casuale: i nodi non controllano tutti nello
        # stesso istante.
        time.sleep(random.uniform(0.0, self.check_interval))
        while not self.stop_event.wait(self.check_interval + random.uniform(0.0, 1.0)):
            with self.cv:
                coordinator = self.coordinator
                busy = self.election_active
            if coordinator is None or coordinator == self.id or busy:
                continue
            if self.coordinator_reachable(coordinator):
                continue
            with self.cv:
                # Ricontrollo: nel frattempo potrebbe essere arrivato un nuovo
                # COORDINATOR oppure un ELECTION da un altro nodo.
                if self.coordinator != coordinator or self.election_active:
                    continue
                self.coordinator = None
            self.log("TIMEOUT: il coordinatore P{} non risponde -> GUASTO".format(coordinator),
                     "TIMEOUT")
            self.start_election("guasto del coordinatore P{}".format(coordinator))

    def coordinator_reachable(self, coordinator):
        """
        Tenta di contattare il coordinatore per AL MASSIMO T secondi.
        Ritorna True appena il contatto riesce, False se scade il timeout T.
        """
        deadline = time.monotonic() + self.T
        warned = False
        while not self.stop_event.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False                      # timeout T scaduto
            try:
                with socket.create_connection(self.address_of(coordinator),
                                              timeout=min(0.5, remaining)):
                    pass
                if warned:
                    self.log("Il coordinatore P{} ha risposto".format(coordinator), "INFO")
                return True
            except OSError:
                if not warned:
                    self.log("Il coordinatore P{} non risponde: riprovo fino a T = {:.1f}s"
                             .format(coordinator, self.T), "ERROR")
                    warned = True
                self.stop_event.wait(min(0.25, max(0.0, deadline - time.monotonic())))
        return True

    # =========================================================================
    # COMANDI DA TASTIERA (terminale del nodo)
    # =========================================================================
    def command_loop(self):
        """e = avvia elezione, s = stato, q = termina il nodo."""
        while not self.stop_event.is_set():
            try:
                line = sys.stdin.readline()
            except (OSError, ValueError, EOFError):
                return
            if line == "":
                return  # stdin chiuso (es. avvio in background): nessun comando
            cmd = line.strip().lower()
            if cmd in ("e", "elezione", "election"):
                self.start_election("avviata da tastiera")
            elif cmd in ("s", "stato", "status"):
                with self.cv:
                    coord = "P{}".format(self.coordinator) if self.coordinator else "sconosciuto"
                    active = "si" if self.election_active else "no"
                self.log("Stato: coordinatore = {}, elezione in corso = {}".format(coord, active))
            elif cmd in ("q", "quit", "esci"):
                self.stop_event.set()   # il thread principale esegue shutdown()
                return
            elif cmd:
                self.log("Comandi: e = avvia elezione | s = stato | q = termina", "DIM")

    # =========================================================================
    # AVVIO E ARRESTO DEL NODO
    # =========================================================================
    def banner(self):
        line = "=" * 64
        title = "\033]0;P{} - Bully - porta {}\007".format(self.id, self.port)
        if self.use_colors and sys.stdout.isatty():
            sys.stdout.write(title)  # titolo della finestra del terminale = nodo
        print(line)
        print("  NODO P{}   (ID = {})   in ascolto su {}:{}".format(self.id, self.id,
                                                                   self.host, self.port))
        print("  Algoritmo del Bullo  -  T = {:.1f}s (ANSWER)  T' = {:.1f}s (COORDINATOR)"
              .format(self.T, self.T_PRIME))
        print("  Comandi: e = avvia elezione | s = stato | q / Ctrl+C = termina")
        print(line, flush=True)

    def shutdown(self):
        """Terminazione del nodo: chiude la porta, cosi' gli altri nodi non
        riescono piu' a contattarlo (e' cio' che accade a P5 con Ctrl+C).
        Dopo la chiusura il nodo non invia ne' riceve piu' alcun messaggio."""
        self.stop_event.set()
        with self.cv:
            self.cv.notify_all()
        if self.server_socket:
            try:
                self.server_socket.close()
            except OSError:
                pass
        self.log("*** processo terminato ***", "TIMEOUT")
        if self.log_file:
            self.log_file.close()
            self.log_file = None


def parse_args():
    p = argparse.ArgumentParser(
        description="Nodo del sistema distribuito con Algoritmo del Bullo (P1..P5).")
    p.add_argument("id", type=int, choices=ALL_IDS, help="ID del nodo (1..5)")
    p.add_argument("--avvia-elezione", action="store_true",
                   help="avvia automaticamente un'elezione dopo --ritardo secondi")
    p.add_argument("--ritardo", type=float, default=3.0,
                   help="secondi di attesa prima dell'elezione automatica (default 3)")
    p.add_argument("--T", dest="t_answer", type=float, default=DEFAULT_T,
                   help="timeout T: attesa massima delle ANSWER (default %(default)s s)")
    p.add_argument("--T1", dest="t_coordinator", type=float, default=DEFAULT_T_PRIME,
                   help="timeout T': attesa massima del COORDINATOR (default %(default)s s)")
    p.add_argument("--intervallo", type=float, default=DEFAULT_CHECK_INTERVAL,
                   help="intervallo di verifica del coordinatore (default %(default)s s)")
    p.add_argument("--host", default=DEFAULT_HOST, help="indirizzo (default 127.0.0.1)")
    p.add_argument("--porta-base", type=int, default=DEFAULT_BASE_PORT,
                   help="porta del nodo Pi = porta-base + i (default 5000)")
    p.add_argument("--log-file", default=None, help="copia dei log anche su file")
    p.add_argument("--no-colori", action="store_true", help="disattiva i colori ANSI")
    return p.parse_args()


def main():
    args = parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    use_colors = not args.no_colori and sys.stdout.isatty()
    if use_colors and os.name == "nt":
        os.system("")  # abilita le sequenze ANSI nel terminale di Windows

    node = BullyNode(args.id, args.host, args.porta_base, args.t_answer,
                     args.t_coordinator, args.intervallo, use_colors, args.log_file)
    node.banner()
    try:
        node.start_server()
    except OSError as e:
        print("Impossibile aprire la porta {}: {}".format(node.port, e), flush=True)
        sys.exit(1)
    node.log("Nodo attivo. Coordinatore: nessuno (non predefinito)")

    # Ctrl+C (SIGINT) e SIGTERM terminano il nodo in modo pulito.
    def on_terminate(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGINT, signal.default_int_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, on_terminate)

    threading.Thread(target=node.monitor_coordinator, name="monitor", daemon=True).start()
    threading.Thread(target=node.command_loop, name="comandi", daemon=True).start()
    if args.avvia_elezione:
        def delayed_start():
            if not node.stop_event.wait(args.ritardo):
                node.start_election("avvio automatico (--avvia-elezione)")
        threading.Thread(target=delayed_start, daemon=True).start()

    try:
        while not node.stop_event.is_set():
            time.sleep(0.2)   # il thread principale resta interrompibile da Ctrl+C
    except KeyboardInterrupt:
        pass
    finally:
        node.shutdown()
    os._exit(0)


if __name__ == "__main__":
    main()
