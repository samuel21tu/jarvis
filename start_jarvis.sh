#!/bin/bash

# Define as cores do JARVIS (Ciano Neon)
CYAN='\033[0;36m'
AMBER='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${CYAN}=== INICIANDO PROTOCOLOS DO JARVIS-NEXUS ===${NC}"

# Verifica se venv existe, senao cria
if [ ! -d "venv" ]; then
    echo -e "${CYAN}[SISTEMA] Criando matriz de ambiente virtual (venv)...${NC}"
    python3 -m venv venv
fi

# Ativa venv
echo -e "${CYAN}[SISTEMA] Ativando ambiente virtual...${NC}"
source venv/bin/activate

# Instala dependencias
echo -e "${CYAN}[SISTEMA] Verificando integridade das dependências...${NC}"
pip install -r requirements.txt -q

# Inicia o Hub (servidor central)
echo -e "${CYAN}[CÉREBRO] Iniciando Hub Neural (FastAPI) na porta 8080...${NC}"
uvicorn src.hub.jarvis_hub:app --host 127.0.0.1 --port 8080 &
HUB_PID=$!

# Aguarda o Hub iniciar
sleep 3

# Inicia o Node (agente do PC)
echo -e "${CYAN}[CORPO] Conectando Nó de Execução local...${NC}"
python src/node/jarvis_node.py &
NODE_PID=$!

# Inicia o servidor para o Frontend Web (Interface Holografica)
echo -e "${CYAN}[VISOR] Carregando Interface Holográfica na porta 8000...${NC}"
cd src/mobile
python3 -m http.server 8000 &
FRONT_PID=$!

echo -e "\n${CYAN}====== SISTEMA 100% ONLINE ======${NC}"
echo -e "${AMBER}Acesse o Painel de Controle pelo seu navegador em: ${NC}http://localhost:8000"
echo -e "${CYAN}=================================${NC}"
echo -e "Para desligar o Jarvis, feche este terminal ou pressione Ctrl+C"

# Mantém o script rodando e captura Ctrl+C para matar os subprocessos
trap "echo -e '\n${AMBER}[SISTEMA] Desligando sistemas e limpando memória...${NC}'; kill $HUB_PID $NODE_PID $FRONT_PID; exit" SIGINT SIGTERM

wait
