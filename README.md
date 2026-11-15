# Elezione del Coordinatore con l'Algoritmo del Bullo

**Progetto finale – Progetto 2.** Sistema distribuito di **5 nodi indipendenti (P1…P5)** che eleggono un coordinatore con il **Bully Algorithm**:

1. **Prima elezione**: avviata da P1, termina con **P5** coordinatore. P5 lo diventa solo tramite l'algoritmo, non per assegnazione iniziale.
2. **Guasto di P5**: il processo viene terminato con **Ctrl+C**.
3. **Seconda elezione**: i nodi rilevano il guasto per timeout e **P4** diventa il nuovo coordinatore.

Ogni nodo è un processo separato, eseguito in un terminale distinto, che comunica **solo tramite messaggi su socket TCP in localhost**. Non c'è memoria condivisa e non c'è un coordinatore predefinito. Sono implementati **solo** i messaggi `ELECTION`, `ANSWER` e `COORDINATOR`, con i timeout reali **T** e **T′**.

---

## Video dimostrativo

📹 **[video/demo_bully.mp4](video/demo_bully.mp4)**: registrazione continua dello schermo, **senza tagli** (circa 1 min e 35 s, 1920×1080).

Il video mostra i 5 nodi, ognuno in una finestra di terminale separata con il titolo `Pi - Bully - porta 500i`. Il sesto riquadro ("Regia demo") descrive la fase in corso e mostra un orologio continuo, che prova l'assenza di tagli.

| Momento | Cosa si vede |
|---|---|
| 0:00 – 0:28 | Apertura dei 5 terminali e avvio dei nodi (`python3 bully_node.py 1` … `5`) |
| ~0:32 | **Fase 1**: in P1 si digita `e` + Invio e parte l'elezione |
| ~0:32 – 0:34 | Messaggi ELECTION/ANSWER a cascata. P5: "Nessun nodo con ID superiore", poi "Mi dichiaro COORDINATORE". P1…P4 ricevono COORDINATOR da P5 |
| ~0:45 | Comando `s` su P1…P4: tutti riportano `coordinatore = P5` |
| ~1:02 | **Fase 2**: **Ctrl+C** nel terminale di P5 (`^C … *** processo terminato ***`) |
| ~1:02 – 1:06 | I nodi non riescono a contattare P5 e scade il **timeout T** (P5 considerato guasto). Gli ELECTION verso P5 non vengono consegnati |
| ~1:06 | **Fase 3**: P4 non riceve risposta da P5 entro T e si dichiara COORDINATORE. P1, P2, P3 ricevono COORDINATOR da P4 |
| ~1:21 | Comando `s` su P1…P4: tutti riportano `coordinatore = P4, elezione in corso = no` |

---

## Istruzioni di Esecuzione

### 1.1 Linguaggio e ambiente
- **Linguaggio:** Python 3.
- **Versione:** Python **3.8 o superiore** (sviluppato e verificato con Python 3.13).
- **Sistema operativo:** qualsiasi (Windows 10/11, macOS, Linux). Tutti i nodi girano su `127.0.0.1`.

### 1.2 Librerie e dipendenze
Solo **libreria standard** di Python: `socket`, `threading`, `json`, `argparse`, `time`, `datetime`, `signal`, `os`, `sys`, `random`.
**Non ci sono dipendenze esterne** e non serve installare nulla (nessun `pip install`).

### 1.3 Compilazione
**Non necessaria**: Python è interpretato. Non servono file di configurazione: porte e timeout hanno valori predefiniti nel codice e si possono modificare da riga di comando (vedi [Opzioni](#opzioni-da-riga-di-comando)).

### 1.4 Avvio dei nodi
Aprire **5 terminali** nella cartella del progetto ed eseguire un comando per terminale:

| Terminale | Nodo | Comando (Windows) | Comando (macOS / Linux) | Indirizzo |
|---|---|---|---|---|
| Terminale 1 | P1 | `python bully_node.py 1` | `python3 bully_node.py 1` | `127.0.0.1:5001` |
| Terminale 2 | P2 | `python bully_node.py 2` | `python3 bully_node.py 2` | `127.0.0.1:5002` |
| Terminale 3 | P3 | `python bully_node.py 3` | `python3 bully_node.py 3` | `127.0.0.1:5003` |
| Terminale 4 | P4 | `python bully_node.py 4` | `python3 bully_node.py 4` | `127.0.0.1:5004` |
| Terminale 5 | P5 | `python bully_node.py 5` | `python3 bully_node.py 5` | `127.0.0.1:5005` |

> Su Windows, se il comando `python` non è disponibile, usare `py` (es. `py bully_node.py 1`).

**Ordine di avvio:** i nodi si possono avviare in qualsiasi ordine, ma **tutti e 5 devono essere attivi prima di avviare la prima elezione**. Ogni nodo stampa `Nodo attivo` quando è pronto.

**Esecuzione dello scenario richiesto:**
1. **Fase 1 (prima elezione).** Nel **terminale di P1** digitare `e` e premere **Invio**. P5 viene eletto e tutti i nodi registrano `Coordinatore registrato: P5`.
   In alternativa si può avviare P1 per ultimo con `python bully_node.py 1 --avvia-elezione`: l'elezione parte da sola dopo 3 secondi.
2. **Fase 2 (guasto).** Nel **terminale di P5** premere **Ctrl+C**. P5 stampa `*** processo terminato ***` e smette di rispondere.
3. **Fase 3 (nuova elezione).** Non serve fare nulla. Entro qualche secondo un nodo rileva il timeout e avvia l'elezione, e P4 si dichiara coordinatore.
4. (Facoltativo) In qualsiasi terminale digitare `s` + Invio per vedere lo stato del nodo (coordinatore noto, elezione in corso).

**Comandi da tastiera** nel terminale di ogni nodo: `e` avvia un'elezione · `s` mostra lo stato · `q` (oppure Ctrl+C) termina il nodo.

**Script di avvio facoltativi** (aprono 5 finestre, una per nodo):
- Windows: doppio clic su `scripts\avvia_windows.bat`
- macOS: `bash scripts/avvia_macos.sh`
- Linux: `bash scripts/avvia_linux.sh` (gnome-terminal, konsole o xterm)
- Linux/macOS con tmux: `bash scripts/avvia_tmux.sh` (5 riquadri, uno per nodo)

### 1.5 Associazione nodo–terminale
- Il nodo eseguito in un terminale è determinato dall'**argomento del comando**: `bully_node.py 3` avvia **P3**, che ascolta sulla porta **5000 + 3 = 5003**. Il Terminale *i* esegue quindi il nodo P*i*.
- All'avvio ogni nodo stampa un'intestazione con il proprio nome, ID e porta:
  ```
  ================================================================
    NODO P3   (ID = 3)   in ascolto su 127.0.0.1:5003
    Algoritmo del Bullo  -  T = 2.0s (ANSWER)  T' = 6.0s (COORDINATOR)
    Comandi: e = avvia elezione | s = stato | q / Ctrl+C = termina
  ================================================================
  ```
- **Ogni riga di log inizia con l'identificativo del nodo**, colorato in modo diverso per ogni nodo, seguito dall'orario al millisecondo, ad esempio `[P3] 23:07:45.291  *** AVVIO ELEZIONE ***`.
- Il **titolo della finestra** del terminale diventa `P3 - Bully - porta 5003`, anche negli script di avvio per Windows e Linux.

---

## Come funziona

### Messaggi (gli unici implementati)

| Messaggio | Da → A | Significato |
|---|---|---|
| `ELECTION` | nodo → tutti i nodi con ID **maggiore** | "Indico un'elezione: c'è qualcuno più forte di me?" |
| `ANSWER` | nodo con ID maggiore → mittente di ELECTION | "Ci sono io: ritirati, ci penso io" |
| `COORDINATOR` | nuovo coordinatore → tutti i nodi con ID **minore** | "Sono il nuovo coordinatore" |

Ogni messaggio viaggia su una connessione TCP dedicata verso la porta del destinatario, come riga JSON: `{"type": "ELECTION", "from": 3}`.

### Timeout (reali, non simulati)
- **T = 2,0 s**, tempo massimo di attesa delle `ANSWER` dopo aver inviato `ELECTION`. Se scade senza risposte, il nodo si proclama coordinatore. T è anche la finestra entro cui un nodo deve riuscire a contattare il coordinatore, altrimenti lo considera guasto.
- **T′ = 6,0 s**, tempo massimo di attesa del `COORDINATOR` dopo aver ricevuto un'`ANSWER`. Se scade, l'elezione viene riavviata: questo copre il caso in cui il nodo che ha risposto si guasta durante l'elezione e garantisce la terminazione.

Entrambi sono attese effettive su una `threading.Condition` con scadenza calcolata su `time.monotonic()`. Un messaggio non consegnato a un nodo spento **non** fa concludere nulla da solo: la decisione arriva solo alla scadenza del timeout.

### Fase 1: elezione iniziale
All'avvio nessun nodo conosce il coordinatore. P1 invia `ELECTION` a P2…P5. Ogni nodo con ID più alto risponde `ANSWER` e avvia la propria elezione (se non ne ha già una in corso). P5 non ha nodi superiori, quindi stampa *"Nessun nodo con ID superiore"*, si dichiara coordinatore e invia `COORDINATOR` a P4, P3, P2, P1. Alla ricezione di `COORDINATOR` ogni nodo **arresta l'elezione in corso** e registra P5: il sistema è in stato stabile.

### Fase 2: rilevazione del guasto di P5
Ogni nodo, a intervalli di circa 2–3 s, tenta di comunicare con il coordinatore aprendo una connessione TCP verso la sua porta. È un semplice tentativo di contatto e non aggiunge un quarto tipo di messaggio. Dopo il Ctrl+C la porta di P5 è chiusa. Se entro **T** il contatto non riesce, il nodo stampa `TIMEOUT: il coordinatore P5 non risponde -> GUASTO`.

### Fase 3: nuova elezione
Il nodo che ha rilevato il guasto (ad esempio P2 o P3) invia `ELECTION` ai nodi con ID più alto, compreso P5, a cui il messaggio non viene consegnato. P4 risponde `ANSWER` e avvia la propria elezione inviando `ELECTION` a P5. Nessuna risposta arriva entro T, quindi P4 stampa `TIMEOUT T (2.0s) scaduto: nessuna risposta da P5`, si dichiara coordinatore e invia `COORDINATOR` a P3, P2, P1.

### Perché non ci sono mai due coordinatori e l'algoritmo termina
- Un nodo si proclama coordinatore **solo** se nessun nodo con ID superiore ha risposto entro T. Finché P5 è attivo risponde in pochi millisecondi, quindi P4 non può proclamarsi. P4 lo fa solo dopo che P5 è terminato (lo verifica anche il test automatico confrontando gli orari).
- Ricevere `COORDINATOR` da un nodo con ID superiore arresta ogni elezione in corso, tramite il contatore di turno `election_round`. Anche un nodo che era coordinatore smette di esserlo.
- Ogni elezione termina in uno di tre modi: proclamazione dopo T, `COORDINATOR` ricevuto entro T′, oppure riavvio dopo T′. Quando i guasti cessano, il nodo attivo con ID massimo si proclama entro T e tutti gli altri ne ricevono il `COORDINATOR`.

Il coordinatore in carica che riceve un `ELECTION` "tardivo" risponde `ANSWER` e conferma il proprio ruolo al mittente con `COORDINATOR`, invece di rifare un'elezione che vincerebbe comunque. È l'esito identico dell'algoritmo, con meno messaggi.

---

## Dove si trova nel codice

Tutto il sistema è in **[`bully_node.py`](bully_node.py)**, commentato in italiano. Parti richieste:

| Requisito | Dove (funzione / sezione) |
|---|---|
| Invio dei messaggi ELECTION / ANSWER / COORDINATOR | `send()`, sezione *SCAMBIO DI MESSAGGI - INVIO* |
| Ricezione e smistamento dei messaggi | `start_server()`, `_accept_loop()`, `_handle_connection()` |
| Gestione di `ELECTION` | `on_election()` |
| Gestione di `ANSWER` | `on_answer()` |
| Gestione di `COORDINATOR` e **arresto delle elezioni in corso** | `on_coordinator()` |
| **Avvio dell'elezione** | `start_election()`, `_begin_election()`, `run_election()` |
| **Timeout T** (attesa ANSWER) | `run_election()`, blocco *2) TIMEOUT T* |
| **Timeout T′** (attesa COORDINATOR) | `run_election()`, blocco *3) TIMEOUT T'* |
| **Proclamazione del coordinatore** | `become_coordinator()` |
| **Gestione del guasto di P5** (rilevazione con timeout T) | `monitor_coordinator()`, `coordinator_reachable()` |
| Terminazione del nodo (Ctrl+C) | `main()`, `shutdown()` |

---

## Verifica automatica

`tests/test_scenario.py` esegue l'intero scenario con 5 processi reali (su porte 6001–6005, per non interferire con un'esecuzione manuale). Termina P5 con SIGINT, lo stesso segnale di Ctrl+C, e controlla i requisiti di correttezza:

```
python3 tests/test_scenario.py
```
```
  [OK]   i 5 nodi sono attivi su porte 6001..6005
FASE 1 - P1 avvia l'elezione
  [OK]   P1..P4 registrano P5 come coordinatore
  [OK]   P5 si dichiara coordinatore tramite l'algoritmo
  [OK]   nessun altro nodo si dichiara coordinatore nella fase 1
FASE 2 - P5 terminato con SIGINT (Ctrl+C)
  [OK]   P5 terminato
FASE 3 - rilevazione del guasto e nuova elezione
  [OK]   P1..P3 registrano P4 come nuovo coordinatore
  [OK]   almeno un nodo rileva il guasto di P5 per timeout
  [OK]   P4 non riceve risposta da P5 entro T
  [OK]   P1 stato finale: coordinatore P4, nessuna elezione in corso
  ...
  [OK]   solo P5 e P4 si sono mai dichiarati coordinatore
  [OK]   P4 si dichiara coordinatore solo DOPO la terminazione di P5
RISULTATO: tutti i controlli superati
```

---

## Esempio di output (estratto reale)

```
[P1] 23:07:13.272  *** AVVIO ELEZIONE *** (avviata da tastiera)
[P1] 23:07:13.275  --> ELECTION inviato a P2
...
[P5] 23:07:13.278  <-- ELECTION ricevuto da P1
[P5] 23:07:13.282  --> ANSWER inviato a P1
[P5] 23:07:13.284  *** AVVIO ELEZIONE *** (ricevuto ELECTION da P1)
[P5] 23:07:13.284  Nessun nodo con ID superiore
[P5] 23:07:13.284  *** Mi dichiaro COORDINATORE ***
[P5] 23:07:13.284  --> COORDINATOR inviato a P4
...
[P5] 23:07:42.969  *** processo terminato ***
[P2] 23:07:45.289  TIMEOUT: il coordinatore P5 non risponde -> GUASTO
[P2] 23:07:45.289  *** AVVIO ELEZIONE *** (guasto del coordinatore P5)
[P2] 23:07:45.289  --> ELECTION a P5 NON consegnato: nodo irraggiungibile
[P4] 23:07:45.290  <-- ELECTION ricevuto da P2
[P4] 23:07:45.290  --> ANSWER inviato a P2
[P4] 23:07:45.290  *** AVVIO ELEZIONE *** (ricevuto ELECTION da P2)
[P4] 23:07:45.290  --> ELECTION a P5 NON consegnato: nodo irraggiungibile
[P4] 23:07:47.291  TIMEOUT T (2.0s) scaduto: nessuna risposta da P5
[P4] 23:07:47.291  *** Mi dichiaro COORDINATORE ***
[P4] 23:07:47.291  --> COORDINATOR inviato a P3
[P3] 23:07:47.291  <-- COORDINATOR ricevuto da P4
[P3] 23:07:47.291  Elezione in corso ARRESTATA (ricevuto COORDINATOR)
[P3] 23:07:47.291  Coordinatore registrato: P4  -> stato stabile
```

---

## Opzioni da riga di comando

```
python bully_node.py ID [--avvia-elezione] [--ritardo S] [--T S] [--T1 S]
                        [--intervallo S] [--host H] [--porta-base N]
                        [--log-file FILE] [--no-colori]
```

| Opzione | Default | Significato |
|---|---|---|
| `ID` | (obbligatorio) | ID del nodo, da 1 a 5 |
| `--avvia-elezione` | disattivo | avvia automaticamente un'elezione dopo `--ritardo` secondi |
| `--ritardo` | 3 | secondi prima dell'elezione automatica |
| `--T` | 2.0 | timeout T (attesa ANSWER e finestra di contatto del coordinatore) |
| `--T1` | 6.0 | timeout T′ (attesa COORDINATOR) |
| `--intervallo` | 2.0 | intervallo dei controlli sul coordinatore (più 0–1 s casuali) |
| `--host` | 127.0.0.1 | indirizzo di ascolto |
| `--porta-base` | 5000 | il nodo P*i* ascolta su `porta-base + i` |
| `--log-file` | — | salva una copia dei log su file |
| `--no-colori` | — | disattiva i colori ANSI |

---

## Struttura del repository

```
bully_node.py              codice del nodo (unico file sorgente, solo libreria standard)
tests/test_scenario.py     verifica automatica dello scenario completo
scripts/avvia_windows.bat  apre 5 finestre del Prompt dei comandi (Windows)
scripts/avvia_macos.sh     apre 5 finestre del Terminale (macOS)
scripts/avvia_linux.sh     apre 5 finestre di terminale (Linux)
scripts/avvia_tmux.sh      sessione tmux con 5 riquadri (Linux/macOS)
video/demo_bully.mp4       video dimostrativo
docs/Consegna_Progetto2_Bully.pdf  documento di consegna (Istruzioni di Esecuzione + link)
```
