#!/usr/bin/env bash
# ==============================================================================
# JARVIS NEXUS // SCRIPT DE AUTOMAÇÃO DE DEPLOY DO HUB NO SERVIDOR CASAOS
# Especialista em DevOps & Infraestrutura
# ==============================================================================

set -euo pipefail
IFS=$'\n\t'

# Definição de cores para telemetria no terminal
CYAN='\033[0;36m'
GREEN='\033[0;32m'
AMBER='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # Sem cor

log()  { printf '%b\n' "${CYAN}$*${NC}"; }
ok()   { printf '%b\n' "${GREEN}$*${NC}"; }
warn() { printf '%b\n' "${AMBER}$*${NC}"; }
err()  { printf '%b\n' "${RED}$*${NC}" >&2; }
die()  { err "$*"; exit 1; }

# Configurações do ambiente de deploy
SERVER_HOST="${SERVER_HOST:-casaos}"
REMOTE_DIR="${REMOTE_DIR:-/home/server/jarvis}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
TARBALL="/tmp/jarvis_deploy.tar.gz"
PTY_SSHPASS="${PROJECT_ROOT}/pty_sshpass.py"
SSH_OPTS=(-o StrictHostKeyChecking=no -o ServerAliveInterval=15 -o ServerAliveCountMax=20)
REMOTE_APP_UID="10001"
REMOTE_APP_GID="10001"

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    die "[ERRO] Variável de ambiente obrigatória ausente: ${name}. Defina-a antes de executar o deploy (ex.: export ${name}='...')."
  fi
}

run_remote() {
  local remote_cmd="$1"
  python3 "${PTY_SSHPASS}" "${CASAOS_PASSWORD}" ssh "${SSH_OPTS[@]}" "${SERVER_HOST}" "${remote_cmd}"
}

run_scp() {
  local src="$1" dst="$2"
  python3 "${PTY_SSHPASS}" "${CASAOS_PASSWORD}" scp "${SSH_OPTS[@]}" "${src}" "${dst}"
}

printf '%b\n' "${CYAN}=====================================================${NC}"
printf '%b\n' "${CYAN}[DEVOPS] JARVIS HUB // PIPELINE DE DEPLOY AUTOMATIZADO${NC}"
printf '%b\n' "${CYAN}=====================================================${NC}"

# 0. Validações locais obrigatórias
require_env CASAOS_PASSWORD

if [[ ! -f "${PTY_SSHPASS}" ]]; then
  die "[ERRO] Executor PTY '${PTY_SSHPASS}' não encontrado."
fi
chmod +x "${PTY_SSHPASS}"

# 1. Verificação de conectividade com o servidor remoto
log "[1/7] Verificando conexão SSH com o servidor (${SERVER_HOST})..."
if ! run_remote "uptime >/dev/null"; then
  die "[ERRO] Não foi possível conectar ao servidor via SSH em '${SERVER_HOST}'."
fi
ok "[OK] Conexão SSH estabelecida com sucesso."

# 2. Empacotamento dos artefatos
log "[2/7] Empacotando artefatos do Hub e Frontend Web..."
rm -f -- "${TARBALL}"
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

TAR_SIZE="$(du -h "${TARBALL}" | cut -f1)"
ok "[OK] Pacote gerado com sucesso: ${TARBALL} (${TAR_SIZE})"

# 3. Preparação remota (diretório, .env, volumes, backup)
log "[3/7] Preparando ambiente remoto em ${SERVER_HOST}:${REMOTE_DIR}..."
run_remote "set -eu; \
REMOTE_DIR=$(printf '%q' "${REMOTE_DIR}"); \
APP_UID=$(printf '%q' "${REMOTE_APP_UID}"); \
APP_GID=$(printf '%q' "${REMOTE_APP_GID}"); \
mkdir -p \"\$REMOTE_DIR\"; \
cd \"\$REMOTE_DIR\"; \
if [ ! -f .env ]; then echo '[CASAOS][ERRO] Arquivo .env ausente no diretório remoto do deploy. Crie-o a partir de .env.example e preencha os segredos antes do deploy.' >&2; exit 1; fi; \
for dir in /DATA/AppData/jarvis/obsidian_vault /DATA/AppData/jarvis/memory; do \
  mkdir -p \"\$dir\"; \
  chown \"\$APP_UID:\$APP_GID\" \"\$dir\" || { echo \"[CASAOS][ERRO] Não foi possível ajustar proprietário de \$dir para \$APP_UID:\$APP_GID. Execute com permissões adequadas no host CasaOS.\" >&2; exit 1; }; \
  chmod 750 \"\$dir\" || true; \
done; \
if [ -f deploy.tar.gz ]; then cp -f deploy.tar.gz deploy.tar.gz.bak; echo '[CASAOS] Backup do artefato anterior: deploy.tar.gz.bak'; fi; \
if docker image inspect jarvis-hub:latest >/dev/null 2>&1; then docker tag jarvis-hub:latest jarvis-hub:rollback; echo '[CASAOS] Backup da imagem atual: jarvis-hub:rollback'; else echo '[CASAOS] Nenhuma imagem jarvis-hub:latest anterior encontrada; backup de imagem ignorado.'; fi"
ok "[OK] Ambiente remoto preparado (diretório, .env, volumes e backup)."

# 4. Transferência segura
log "[4/7] Transferindo pacote para ${SERVER_HOST}:${REMOTE_DIR}/deploy.tar.gz..."
run_remote "mkdir -p $(printf '%q' "${REMOTE_DIR}")"
run_scp "${TARBALL}" "${SERVER_HOST}:${REMOTE_DIR}/deploy.tar.gz"
ok "[OK] Transferência concluída."

# 5. Deploy remoto (extract, build, up)
log "[5/7] Executando extração, build e deploy Docker no servidor..."
run_remote "set -eu; \
REMOTE_DIR=$(printf '%q' "${REMOTE_DIR}"); \
cd \"\$REMOTE_DIR\"; \
tar -xzf deploy.tar.gz; \
if [ ! -f .env ]; then echo '[CASAOS][ERRO] Arquivo .env ausente antes do docker compose up. Abortando.' >&2; exit 1; fi; \
echo '[CASAOS] Reconstruindo imagem Docker jarvis-hub:latest...'; \
docker compose build jarvis-hub; \
echo '[CASAOS] Reiniciando container jarvis-hub...'; \
docker compose up -d --force-recreate --remove-orphans jarvis-hub"
ok "[OK] Build e deploy concluídos no Docker."

# 6. Verificação de saúde
log "[6/7] Realizando Health Check dos serviços..."
sleep 3

CHECK_RUNNING="$(run_remote "docker inspect -f '{{.State.Running}}' jarvis-hub 2>/dev/null || echo false" | tr -d '\r' | tail -n 1)"
if [[ "${CHECK_RUNNING}" == "true" ]]; then
  ok "[OK] Container jarvis-hub em execução."
else
  warn "[AVISO] Container jarvis-hub não está em execução (estado: ${CHECK_RUNNING})."
  warn "[ROLLBACK] Para rollback: ssh ${SERVER_HOST} 'cd ${REMOTE_DIR} && docker tag jarvis-hub:rollback jarvis-hub:latest && docker compose up -d --force-recreate --remove-orphans jarvis-hub'"
  die "[ERRO] Deploy falhou no healthcheck de container."
fi

CHECK_INTERNAL="$(run_remote "curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:8080/" | tr -d '\r' | tail -n 1)"
if [[ "${CHECK_INTERNAL}" == "200" ]]; then
  ok "[OK] Health Check interno HTTP (127.0.0.1:8080/): 200"
else
  warn "[AVISO] Health Check interno HTTP retornou: ${CHECK_INTERNAL}"
fi

CHECK_WS="$(run_remote "curl -s -o /dev/null -w '%{http_code}' --max-time 10 -H 'Connection: Upgrade' -H 'Upgrade: websocket' -H 'Sec-WebSocket-Version: 13' -H 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==' http://127.0.0.1:8080/ws/node/healthcheck" | tr -d '\r' | tail -n 1)"
case "${CHECK_WS}" in
  101)
    ok "[OK] Health Check WS (/ws/node/healthcheck): handshake 101"
    ;;
  400|401|403|426)
    ok "[OK] Health Check WS (/ws/node/healthcheck): endpoint acessível (HTTP ${CHECK_WS})"
    ;;
  404)
    warn "[AVISO] Health Check WS retornou 404 em /ws/node/healthcheck; verifique roteamento WS."
    ;;
  *)
    warn "[AVISO] Health Check WS retornou status inesperado: ${CHECK_WS}"
    ;;
esac

CHECK_EXTERNAL="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 https://jarvis.samuel21tu.space/ || echo 'FALHA')"
if [[ "${CHECK_EXTERNAL}" == "200" ]]; then
  ok "[OK] Conectividade externa (https://jarvis.samuel21tu.space/): HTTP 200"
else
  warn "[AVISO] Verificação externa retornou status: ${CHECK_EXTERNAL}"
fi

# 7. Limpeza e instruções
log "[7/7] Limpeza local e instruções de rollback..."
rm -f -- "${TARBALL}"

if [[ "${CHECK_INTERNAL}" != "200" ]]; then
  warn "[ROLLBACK] Rollback sugerido: ssh ${SERVER_HOST} 'cd ${REMOTE_DIR} && docker tag jarvis-hub:rollback jarvis-hub:latest && docker compose up -d --force-recreate --remove-orphans jarvis-hub'"
  die "[ERRO] Deploy concluído com falha no healthcheck HTTP interno."
fi

printf '\n%b\n' "${GREEN}=====================================================${NC}"
printf '%b\n' "${GREEN}[SUCESSO] DEPLOY DO JARVIS CONCLUÍDO COM SUCESSO!${NC}"
printf '%b\n' "${GREEN}Endereço: https://jarvis.samuel21tu.space/${NC}"
printf '%b\n' "${AMBER}[ROLLBACK] Em caso de regressão: ssh ${SERVER_HOST} 'cd ${REMOTE_DIR} && docker tag jarvis-hub:rollback jarvis-hub:latest && docker compose up -d --force-recreate --remove-orphans jarvis-hub'${NC}"
printf '%b\n' "${GREEN}=====================================================${NC}"
