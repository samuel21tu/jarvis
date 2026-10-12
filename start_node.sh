#!/bin/bash
# Conecta este PC (nó de execução) ao Jarvis Hub hospedado no CasaOS.
# Uso: ./start_node.sh            -> rede local (192.168.1.92)
#      NEXUS_URL=wss://dominio ./start_node.sh -> acesso remoto
set -euo pipefail
cd "$(dirname "$0")"

export NEXUS_URL="${NEXUS_URL:-ws://192.168.1.92:8080}"
export NODE_ID="${NODE_ID:-cachyos_linux}"

if [ ! -d venv ]; then
    python3 -m venv venv
    ./venv/bin/pip install -q -r requirements.txt
fi

echo "[JARVIS] Conectando nó '$NODE_ID' ao servidor $NEXUS_URL ..."
exec ./venv/bin/python src/node/jarvis_node.py
