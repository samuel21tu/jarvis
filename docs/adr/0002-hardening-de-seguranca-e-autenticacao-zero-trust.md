# ADR-0002: Hardening de Segurança, Autenticação de WebSockets e Defesa em Profundidade

## Status
Aceito

## Contexto
O ecossistema JARVIS opera com um Hub central (FastAPI em Docker/CasaOS), nós de execução locais nos desktops (CachyOS/Linux) e um HUD web/mobile exposto via túnel público (`https://jarvis.samuel21tu.space`).
A análise do catálogo de habilidades de segurança revelou vulnerabilidades críticas que precisavam de remediação imediata:
1. Credenciais e chaves de API hardcoded no código fonte (`src/hub/core/config.py`).
2. Ausência de validação de autenticação no endpoint WebSocket dos nós (`/ws/node/{node_id}`).
3. Política CORS com curinga permissivo `allow_origins=["*"]` associada a `allow_credentials=True`.
4. Risco de injeção de comandos no nó host através da função `execute_command()` com `shell=True`.
5. Execução do contêiner Docker como usuário `root`.

## Decisão
1. **Remoção de Segredos Estáticos:** Eliminar todas as chaves de API do código-fonte e carregar valores estritamente de variáveis de ambiente (`.env`). Criar `.gitignore` e `.env.example`.
2. **Autenticação em Tempo Constante no WebSocket:** Exigir o cabeçalho `nexus-api-key` ou query parameter autenticado no handshake de `/ws/node/{node_id}`, validado com `hmac.compare_digest` para neutralizar ataques de temporização (*timing attacks*).
3. **Restrição de CORS & Cabeçalhos HTTP:** Limitar CORS estritamente às origens do domínio de produção e localhost, além de injetar cabeçalhos de segurança (`X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy: strict-origin-when-cross-origin`).
4. **Sanitização de Comandos no Host:** Implementar a função `is_command_safe()` com lista de bloqueio de regex para comandos destrutivos (`rm -rf`, `mkfs`, `dd`, `shutdown`, fork bombs e vazamento de chaves SSH).
5. **Hardening de Docker:** Adicionar usuário sem privilégios `appuser` (UID 10001) no `Dockerfile` e ativar `security_opt: [no-new-privileges:true]` no `docker-compose.yml`.

## Consequências
- **Positivas:** Conformidade com padrões OWASP, eliminação de superfície de ataque não autenticada no WebSocket e prevenção de execuções remotas destrutivas acidentais ou maliciosas.
- **Negativas/Mitigações:** Conexões de nós que não enviarem a chave correta serão rejeitadas com erro 4001, exigindo que o arquivo `.env` do nó esteja sincronizado com o do Hub.
