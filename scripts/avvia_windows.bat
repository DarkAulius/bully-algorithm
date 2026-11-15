@echo off
REM ==========================================================================
REM  Avvio dei 5 nodi su Windows: apre 5 finestre del Prompt dei comandi,
REM  una per nodo. Il titolo di ogni finestra indica il nodo (P1..P5).
REM  Dopo l'avvio, nella finestra di P1 digitare  e  e premere Invio per
REM  avviare la prima elezione.
REM ==========================================================================
cd /d "%~dp0\.."

set PY=python
where python >nul 2>nul || set PY=py

start "P5 - Bully (porta 5005)" cmd /k %PY% bully_node.py 5
start "P4 - Bully (porta 5004)" cmd /k %PY% bully_node.py 4
start "P3 - Bully (porta 5003)" cmd /k %PY% bully_node.py 3
start "P2 - Bully (porta 5002)" cmd /k %PY% bully_node.py 2
start "P1 - Bully (porta 5001)" cmd /k %PY% bully_node.py 1
