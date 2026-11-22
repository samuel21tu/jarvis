# Changelog

Todas as alterações notáveis neste projeto serão documentadas neste arquivo.

O formato baseia-se em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não Publicado] - 2026-11-21

### Modificado
- **Roteador de IA como provedor padrão:** respostas e resumo de memória passam a usar o OmniRoute local (`http://localhost:20128/v1`) por `LLM_ROUTER_BASE_URL` / `LLM_ROUTER_API_KEY` / `LLM_ROUTER_MODEL` (`auto/chat`, reserva `grok-cli/grok-4.7-low`). Gemini foi removido do caminho de inferência, sem fallback.
- **Ativação por palma removida:** detectores de dupla palma e o despertar associado foram retirados do HUD mobile (`src/mobile/app.js`); o microfone continua controlado por toque/voz.

### Segurança
- Validação da URL do roteador: HTTPS obrigatório, bloqueio de localhost/IP privado (SSRF) e allowlist opcional de hosts via `LLM_ROUTER_ALLOWED_HOSTS`.

## [Não Publicado] - 2026-10-12

### Segurança
- **Higienização de Credenciais:** Removidas chaves de API estáticas e hardcoded de `src/hub/core/config.py`, impondo carregamento obrigatório via `.env` ou variáveis de ambiente do host.
- **Blindagem de Repositório:** Criados `.gitignore` robusto para impedir versionamento acidental de `.env`, bases SQLite (`data/`), chaves SSH e caches, e `.env.example` higienizado para documentação de variáveis de ambiente.
- **Proteção de WebSockets:** Implementada validação de autenticação em tempo constante (`hmac.compare_digest`) no handshake do nó local (`/ws/node/{node_id}`) contra `NEXUS_API_KEY`, fechando conexões não autorizadas com código seguro `4001`.
- **Restrição de CORS & Headers:** Configurado CORS estrito com origens confiáveis (`jarvis.samuel21tu.space` e origens locais) substituindo o curinga universal `*`, além da injeção de cabeçalhos de segurança HTTP (`X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy: strict-origin-when-cross-origin`).
- **Sanitização de Comandos no Host:** Implementado mecanismo de validação defensiva `is_command_safe` em `src/node/jarvis_node.py` com bloqueio estrito contra comandos destrutivos (`rm -rf`, `mkfs`, `dd`, `shutdown`, fork bombs e exfiltração de chaves SSH em `~/.ssh/`).
- **Hardening de Contêiner Docker:** Configurado `Dockerfile` para execução como usuário não-privilegiado `appuser` (UID 10001) em vez de `root`, e adicionado `security_opt: [no-new-privileges:true]` em `docker-compose.yml`.
- **Suíte de Testes Automatizados:** Desenvolvida suíte `tests/test_security_hardening.py` para validação contínua de bloqueio de comandos destrutivos, CORS restrito e integridade de configurações.

### Adicionado
- Interação por toque/clique direto no Orb 3D holográfico para alternância de microfone (`handleMicToggle`).
- Ativação da matriz de 6 agentes especializados no Maestri com papéis e skills direcionadas a segurança e arquitetura resiliente.

### Modificado
- Desacoplamento da inicialização de nós de áudio no cliente mobile com desbloqueio síncrono via `unlockAudio` no primeiro toque.
- Prevenção de duplicação de áudio no HUD (`app.js`) com controle atômico por ID sequencial (`speakActionId`).
- Guard-rail no Hub FastAPI (`jarvis_hub.py`) descartando requisições fantasmas com buffers vazios de fala.

### Corrigido
- Orbe preso pulsando e microfone que não reconhecia voz após a primeira resposta: `speakAIResponse()` não chamava `onAISpeechFinished()` quando o áudio enviado pelo servidor terminava, deixando `isAISpeaking` permanentemente `true`. Agora a conclusão do áudio (ou watchdog/falha no decode) limpa a flag e retoma a escuta; adicionado fallback para síntese local se o decode falhar.
- Removido resquício da funcionalidade de palma em `handleMicToggle` (`micUnmutedAt`).
- Loop de silêncio e estado travado em `MUTED` em dispositivos móveis.
- Corrida assíncrona que causava vozes sobrepostas simultâneas do sintetizador TTS.

## [1.0.0] - 2026-10-09

### Adicionado
- Arquitetura distribuída do JARVIS com Hub central (FastAPI/Uvicorn) e Nós de execução desktop.
- HUD holográfico com Three.js/Canvas 2D e telemetria em tempo real.
- Suporte a empacotamento Flatpak (`com.jarvis.Node.json`) e integração com bandeja do sistema (D-Bus SNI / Wayland / X11).
