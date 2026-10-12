#!/usr/bin/env bash
# ==============================================================================
# JARVIS NEXUS // SCRIPT DE AUTOMAÇÃO DE DEPLOY DO HUB NO SERVIDOR CASAOS
# Especialista em DevOps & Infraestrutura
# ==============================================================================

set -euo pipefail

# Definição de cores para telemetria no terminal
CYAN='\033[0;36m'
GREEN='\033[0;32m'
AMBER='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # Sem cor

# Configurações do ambiente de deploy
SERVER_HOST="${SERVER_HOST:-casaos}"
SERVER_PASS="${CASAOS_PASSWORD:-\$samuca123\$}"
REMOTE_DIR="/home/server/jarvis"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARBALL="/tmp/jarvis_deploy.tar.gz"
PTY_SSHPASS="${PROJECT_ROOT}/pty_sshpass.py"
SSH_OPTS="-o StrictHostKeyChecking=no -o ServerAliveInterval=15 -o ServerAliveCountMax=20"

echo -e "${CYAN}=====================================================${NC}"
echo -e "${CYAN}[DEVOPS] JARVIS HUB // PIPELINE DE DEPLOY AUTOMATIZADO${NC}"
echo -e "${CYAN}=====================================================${NC}"

# 1. Verificação de dependências locais
if [ ! -f "${PTY_SSHPASS}" ]; then
    echo -e "${RED}[ERRO] Executor PTY '${PTY_SSHPASS}' não encontrado.${NC}"
    exit 1
fi

chmod +x "${PTY_SSHPASS}"

# 2. Teste de conectividade com o servidor remoto
echo -e "${CYAN}[1/5] Verificando conexão SSH com o servidor (${SERVER_HOST})...${NC}"
if ! python3 "${PTY_SSHPASS}" "${SERVER_PASS}" ssh ${SSH_OPTS} "${SERVER_HOST}" "uptime" > /dev/null 2>&1; then
    echo -e "${RED}[ERRO] Não foi possível conectar ao servidor via SSH em '${SERVER_HOST}'.${NC}"
    exit 1
fi
echo -e "${GREEN}[OK] Conexão SSH estabelecida com sucesso.${NC}"

# 3. Empacotamento dos artefatos
echo -e "${CYAN}[2/5] Empacotando artefatos do Hub e Frontend Web...${NC}"
rm -f "${TARBALL}"

tar -czf "${TARBALL}" \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git' \
    --exclude='.venv' \
    --exclude='venv' \
    --exclude='.flatpak-builder' \
    --exclude='build-dir' \
    -C "${PROJECT_ROOT}" \
    src \
    Dockerfile \
    docker-compose.yml \
    requirements.txt

TAR_SIZE=$(du -h "${TARBALL}" | cut -f1)
echo -e "${GREEN}[OK] Pacote gerado com sucesso: ${TARBALL} (${TAR_SIZE})${NC}"

# 4. Transferência segura para o servidor remoto
echo -e "${CYAN}[3/5] Transferindo pacote para ${SERVER_HOST}:${REMOTE_DIR}/deploy.tar.gz...${NC}"
python3 "${PTY_SSHPASS}" "${SERVER_PASS}" scp ${SSH_OPTS} "${TARBALL}" "${SERVER_HOST}:${REMOTE_DIR}/deploy.tar.gz"
echo -e "${GREEN}[OK] Transferência concluída.${NC}"

# 5. Execução do Deploy Remoto (Descompactação, Build e Up do Docker)
echo -e "${CYAN}[4/5] Executando descompactação e rebuild do container Docker no servidor...${NC}"
REMOTE_CMD="cd ${REMOTE_DIR} && \
tar -xzf deploy.tar.gz && \
echo '[CASAOS] Reconstruindo imagem Docker jarvis-hub:latest...' && \
docker compose build jarvis-hub && \
echo '[CASAOS] Reiniciando container jarvis-hub...' && \
docker compose up -d --force-recreate --remove-orphans jarvis-hub"

python3 "${PTY_SSHPASS}" "${SERVER_PASS}" ssh ${SSH_OPTS} "${SERVER_HOST}" "${REMOTE_CMD}"
echo -e "${GREEN}[OK] Build e deploy concluídos no Docker.${NC}"

# 6. Verificação de Saúde (Health Check)
echo -e "${CYAN}[5/5] Realizando Health Check dos serviços...${NC}"

# Aguarda 3 segundos para estabilização do container
sleep 3

# Healthcheck interno via servidor
CHECK_INTERNAL=$(python3 "${PTY_SSHPASS}" "${SERVER_PASS}" ssh ${SSH_OPTS} "${SERVER_HOST}" "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/")

if [ "${CHECK_INTERNAL}" = "200" ]; then
    echo -e "${GREEN}[OK] Health Check Interno (127.0.0.1:8080): HTTP 200 OK${NC}"
else
    echo -e "${AMBER}[AVISO] Health Check Interno retornou código HTTP: ${CHECK_INTERNAL}${NC}"
fi

# Healthcheck externo via Cloudflare Tunnel
CHECK_EXTERNAL=$(curl -s -o /dev/null -w "%{http_code}" https://jarvis.samuel21tu.space/ || echo "FALHA")

if [ "${CHECK_EXTERNAL}" = "200" ]; then
    echo -e "${GREEN}[OK] Conectividade Externa (https://jarvis.samuel21tu.space/): HTTP 200 OK${NC}"
else
    echo -e "${AMBER}[AVISO] Verificação externa retornou status: ${CHECK_EXTERNAL}${NC}"
fi

# Limpeza local
rm -f "${TARBALL}"

echo -e "\n${GREEN}=====================================================${NC}"
echo -e "${GREEN}[SUCESSO] DEPLOY DO JARVIS CONCLUÍDO COM SUCESSO!${NC}"
echo -e "${GREEN}Endereço: https://jarvis.samuel21tu.space/${NC}"
echo -e "${GREEN}=====================================================${NC}"
