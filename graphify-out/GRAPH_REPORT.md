# Graph Report - jarvis  (2026-11-21)

## Corpus Check
- Corpus is ~32,214 words - fits in a single context window. You may not need a graph.

## Summary
- 621 nodes · 982 edges · 45 communities (24 shown, 21 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 108 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- PTY Command Execution
- Mobile HUD & Telemetry
- Node Console & Commands
- LLM Provider Layer
- Product & Architecture Specs
- ADR Design Decisions
- TTS & Patch Tooling
- Conversation Memory Sync
- Hub Fix Scripts
- Mobile Audio Loop Fix
- Docker Deployment
- Vault Sync & Hashing
- WebSocket Connection Hub
- Voice FSM Tests
- Node Tool Functions
- Mobile Audio Handlers
- Obsidian Brain Storage
- Model Configuration
- Mic Playwright Tests
- Gemini Request Retry
- Speech Recognition Control
- Favicon Visual Identity
- Node HUD Artwork
- TTS Sentence Timing
- Speech Synthesis Fallback
- Holographic Core Rendering
- Telemetry WS Client
- Node Startup Script
- TTS Puppeteer Test
- Retry Error Classification
- Attachment Upload UI
- Hub Deploy Script
- TTS Replacement Patch
- Execute Command Tool
- Obsidian Search Tool
- Read Note Tool
- Conversation Search Tool
- Obsidian Search Schema
- Save Note Schema
- Conversation Search Schema
- Chrome Test Script
- Audio Test Transcript

## God Nodes (most connected - your core abstractions)
1. `MemoryManager` - 18 edges
2. `SNITray` - 17 edges
3. `Changelog do JARVIS (Keep a Changelog / Versionamento Semântico)` - 17 edges
4. `VoiceFSM` - 15 edges
5. `ConnectionManager` - 12 edges
6. `appendLogLine()` - 12 edges
7. `createSpeechRecognizer()` - 12 edges
8. `chat_with_nexus()` - 11 edges
9. `setCoreState()` - 11 edges
10. `jarvis-hub` - 10 edges

## Surprising Connections (you probably didn't know these)
- `Blindagem de Repositório — .gitignore robusto e .env.example higienizado` --semantically_similar_to--> `Segurança de segredos — OPENROUTER_API_KEY nunca commitada/impressa/passada em args/tarball; modelo escolhido de allowlist revisada`  [INFERRED] [semantically similar]
  CHANGELOG.md → docs/openrouter-rollout.md
- `Google Translate TTS — endpoint translate.google.com/translate_tts?client=tw-ob reproduzido com new Audio() em 'modo fantasma'` --semantically_similar_to--> `Web Speech API — SpeechRecognition/webkitSpeechRecognition e SpeechSynthesisUtterance`  [INFERRED] [semantically similar]
  test_tts.html → conductor/tech-stack.md
- `Histórico da Sessão session_952962 — senha sudo recusada, desinstalação Firefox, capacidades, Google Home e análise de imagens` --conceptually_related_to--> `Decisão: Remoção de Segredos Estáticos — eliminar chaves de API do código e carregar de .env; criar .gitignore e .env.example`  [AMBIGUOUS]
  obsidian_vault/Jarvis_Session_session_952962.md → docs/adr/0002-hardening-de-seguranca-e-autenticacao-zero-trust.md
- `Correção de loop de silêncio e estado travado em MUTED em dispositivos móveis` --conceptually_related_to--> `Causa Raiz — continuous=false encerra sessão no mobile; onend chama scheduleRecognitionRestart(320) sem backoff; colisão AudioContext/getUserMedia perde Audio Focus; falta trava de transição na FSM`  [INFERRED]
  CHANGELOG.md → conductor/tracks/bug_mobile_audio_loop/spec.md
- `Arquitetura distribuída do JARVIS — Hub central FastAPI/Uvicorn e Nós de execução desktop` --conceptually_related_to--> `Jarvis Nexus — ecossistema de assistência por IA contextual e multimodal (nós OS, Hub, HUD mobile/web)`  [INFERRED]
  CHANGELOG.md → conductor/product.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Correção do bug de mudo/loop do microfone mobile: causa raiz → FSM → backoff → isolamento → sync App Linux** — conductor_tracks_bug_mobile_audio_loop_spec_causa_raiz, conductor_tracks_bug_mobile_audio_loop_plan_fsm_appjs, conductor_tracks_bug_mobile_audio_loop_plan_backoff, conductor_tracks_bug_mobile_audio_loop_plan_trava_atomica, conductor_tracks_bug_mobile_audio_loop_plan_isolamento_audio, conductor_tracks_bug_mobile_audio_loop_plan_webkitgtk, 0001_unlockaudio [INFERRED 0.85]
- **Defesa em profundidade ADR-0002: segredos, WebSocket, CORS, comandos e Docker** — 0002_segredos_estaticos, 0002_auth_websocket, 0002_cors_headers, 0002_is_command_safe, 0002_docker_hardening, changelog_suite_testes_seguranca [EXTRACTED 1.00]
- **Rollout controlado do provedor LLM: Gemini padrão, OpenRouter preparado, segredos e rollback** — conductor_tech_stack_gemini_openrouter, openrouter_escopo, openrouter_variaveis, openrouter_sequencia, openrouter_validacoes [INFERRED 0.85]

## Communities (45 total, 21 thin omitted)

### Community 0 - "PTY Command Execution"
Cohesion: 0.06
Nodes (16): execute_pty(), _chrome_running(), create_image(), exit_action(), kill_chrome(), launch_chrome(), notify(), run_cmd() (+8 more)

### Community 1 - "Mobile HUD & Telemetry"
Cohesion: 0.04
Nodes (47): barCpu, barGpu, barNet, barRam, barTemp, btnF11Link, btnFullscreen, btnHelp (+39 more)

### Community 2 - "Node Console & Commands"
Cohesion: 0.09
Nodes (14): test(), execute_command(), get_distro_name(), get_realtime_metrics(), get_system_status(), handle_server_message(), is_command_safe(), run_node() (+6 more)

### Community 3 - "LLM Provider Layer"
Cohesion: 0.07
Nodes (8): _data_url(), LLMProviderError, LLMResponse, mensagens_openrouter(), OllamaProvider, OpenRouterProvider, _schema_ferramenta(), ToolCall

### Community 4 - "Product & Architecture Specs"
Cohesion: 0.07
Nodes (32): Arquitetura distribuída do JARVIS — Hub central FastAPI/Uvicorn e Nós de execução desktop, Blindagem de Repositório — .gitignore robusto e .env.example higienizado, HUD holográfico — Three.js/Canvas 2D com telemetria em tempo real, Jarvis Nexus — Definição de Produto, Jarvis Nexus — ecossistema de assistência por IA contextual e multimodal (nós OS, Hub, HUD mobile/web), Objetivos do Produto — controle por voz/texto de baixa latência, arquitetura distribuída de nós, estabilidade mobile e HUD web, Obsidian Vault — memória/persistência de histórico de conversa do assistente, Jarvis Nexus — Stack Tecnológica (+24 more)

### Community 5 - "ADR Design Decisions"
Cohesion: 0.09
Nodes (21): Restrição de CORS & Headers — origens confiáveis no lugar de '*' e headers X-Content-Type-Options/X-Frame-Options/Referrer-Policy, Changelog do JARVIS (Keep a Changelog / Versionamento Semântico), Guard-rail no Hub FastAPI (jarvis_hub.py) — descarta requisições fantasmas com buffers de fala vazios, Hardening de Contêiner Docker — appuser UID 10001 no Dockerfile e security_opt no-new-privileges:true, Matriz de 6 agentes especializados no Maestri — papéis e skills voltadas a segurança e arquitetura resiliente, Orbe 3D Holográfico — handleMicToggle por toque/clique para alternar microfone, Proteção de WebSockets — hmac.compare_digest no handshake /ws/node/{node_id}, conexões não autorizadas com código 4001, Sanitização de Comandos no Host — is_command_safe bloqueia rm -rf, mkfs, dd, shutdown, fork bombs e exfiltração de ~/.ssh em src/node/jarvis_node.py (+13 more)

### Community 6 - "TTS & Patch Tooling"
Cohesion: 0.08
Nodes (7): build_system_prompt(), chat_with_nexus(), _fetch_elevenlabs_audio(), generate_tts_audio_base64(), security_and_cache_middleware(), websocket_mobile_endpoint(), websocket_node_endpoint()

### Community 8 - "Hub Fix Scripts"
Cohesion: 0.11
Nodes (7): main(), main(), main(), main(), main(), main(), main()

### Community 9 - "Mobile Audio Loop Fix"
Cohesion: 0.11
Nodes (25): Empacotamento Flatpak com.jarvis.Node.json — integração com bandeja do sistema via D-Bus SNI / Wayland / X11, Correção de loop de silêncio e estado travado em MUTED em dispositivos móveis, Web Audio API — AudioContext/AnalyserNode para reatividade e visualizador de frequências, bug_mobile_audio_loop — Bug Crítico: Correção de Mudo e Loop Infinito no Microfone Mobile (Concluído; Antigravity 2, 3, 4), Backoff adaptativo com limite de tentativas em scheduleRecognitionRestart — evita cascata de 320ms, Plano de Implementação — Correção do Bug de Mudo e Loop no Microfone Mobile, FSM estrita em src/mobile/app.js — estados MUTED, LISTENING, PROCESSING, SPEAKING, COOLDOWN, Desacoplar Web Audio API de entrada no mobile — liberar hardware exclusivamente ao reconhecimento de voz (+17 more)

### Community 10 - "Docker Deployment"
Cohesion: 0.08
Nodes (25): en_us, build, container_name, env_file, environment, image, ports, restart (+17 more)

### Community 11 - "Vault Sync & Hashing"
Cohesion: 0.13
Nodes (9): apply_synced_summary(), compare_vault_manifests(), compute_file_hash(), compute_vault_manifest(), get_memory_state(), get_messages_for_sync(), insert_synced_messages(), read_vault_note_raw() (+1 more)

### Community 13 - "Voice FSM Tests"
Cohesion: 0.28
Nodes (3): assert, runTests(), VoiceFSM

### Community 14 - "Node Tool Functions"
Cohesion: 0.12
Nodes (6): execute_command(), get_system_status(), get_system_status_schema(), read_obsidian_note_schema(), save_obsidian_note(), set_remote_server_dispatchers()

### Community 15 - "Mobile Audio Handlers"
Cohesion: 0.25
Nodes (16): appendLogLine(), handleFirstUserGesture(), handleInterruptToggle(), handleMicToggle(), initUserAudioInput(), onAISpeechFinished(), playAudioBase64WebAudio(), setCoreState() (+8 more)

### Community 18 - "Mic Playwright Tests"
Cohesion: 0.22
Nodes (5): devDependencies, playwright@^1.64.0, playwright, { chromium, devices }, { chromium, devices }

### Community 19 - "Gemini Request Retry"
Cohesion: 0.22
Nodes (4): execute_model_request(), _cliente_gemini(), safe_generate_content(), summarize_conversation()

### Community 20 - "Speech Recognition Control"
Cohesion: 0.31
Nodes (9): createSpeechRecognizer(), dedupeTranscript(), dispatchUserVoiceCommand(), extractWakeWordCommand(), isSleepCommand(), isSpeechRecognitionSupported(), scheduleRecognitionRestart(), sendUserCommand() (+1 more)

### Community 22 - "Favicon Visual Identity"
Cohesion: 0.60
Nodes (5): Circuit Board Background Pattern, Circular AI Core Status HUD, Hexagonal Honeycomb Core Motif, Neon Blue Sci-Fi HUD Theme, AI Status Readout Text Elements

### Community 23 - "Node HUD Artwork"
Cohesion: 0.83
Nodes (4): Concentric Glowing Rings with Tick Marks, Central Hexagonal Honeycomb Core, Circular Sci-Fi HUD Interface, Status Readouts (BADGE STATUS: ACTIVE, PROCESSING: 94%, SYSTEM STATUS: NORMAL)

### Community 25 - "Speech Synthesis Fallback"
Cohesion: 0.50
Nodes (4): cleanTextForSpeech(), fallbackToWebSpeech(), loadVoices(), speakNextSentence()

### Community 26 - "Holographic Core Rendering"
Cohesion: 0.50
Nodes (4): detectClapAudio(), project3D(), renderHoloCore(), rotate3D()

### Community 27 - "Telemetry WS Client"
Cohesion: 0.50
Nodes (4): handleTelemetry(), initWebSocket(), scheduleWsReconnect(), updateHardwareMetrics()

### Community 28 - "Node Startup Script"
Cohesion: 0.50
Nodes (3): NEXUS_URL, NODE_ID, start_node.sh script

### Community 31 - "Attachment Upload UI"
Cohesion: 0.67
Nodes (3): clearPendingAttachments(), handleSelectedFiles(), updateFileStatusUI()

## Ambiguous Edges - Review These
- `Decisão: Remoção de Segredos Estáticos — eliminar chaves de API do código e carregar de .env; criar .gitignore e .env.example` → `Histórico da Sessão session_952962 — senha sudo recusada, desinstalação Firefox, capacidades, Google Home e análise de imagens`  [AMBIGUOUS]
  obsidian_vault/Jarvis_Session_session_952962.md · relation: conceptually_related_to

## Knowledge Gaps
- **15 isolated node(s):** `NEXUS_URL`, `NODE_ID`, `Suíte de Testes Automatizados — tests/test_security_hardening.py valida bloqueio de comandos, CORS e configurações`, `Matriz de 6 agentes especializados no Maestri — papéis e skills voltadas a segurança e arquitetura resiliente`, `Objetivos do Produto — controle por voz/texto de baixa latência, arquitetura distribuída de nós, estabilidade mobile e HUD web` (+10 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 264 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **21 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MemoryManager` connect `Conversation Memory Sync` to `Memory & Vault Modules`?**
  _High betweenness centrality (0.046) - this node is a cross-community bridge._
- **What connects `NEXUS_URL`, `NODE_ID`, `Suíte de Testes Automatizados — tests/test_security_hardening.py valida bloqueio de comandos, CORS e configurações` to the rest of the system?**
  _15 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `PTY Command Execution` be split into smaller, more focused modules?**
  _Cohesion score 0.06127946127946128 - nodes in this community are weakly interconnected._
- **Why does `ConnectionManager` connect `WebSocket Connection Hub` to `TTS & Patch Tooling`?**
  _High betweenness centrality (0.036) - this node is a cross-community bridge._
- **Should `Mobile HUD & Telemetry` be split into smaller, more focused modules?**
  _Cohesion score 0.03773584905660377 - nodes in this community are weakly interconnected._
- **Should `Node Console & Commands` be split into smaller, more focused modules?**
  _Cohesion score 0.08710801393728224 - nodes in this community are weakly interconnected._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `Decisão: Remoção de Segredos Estáticos — eliminar chaves de API do código e carregar de .env; criar .gitignore e .env.example` and `Histórico da Sessão session_952962 — senha sudo recusada, desinstalação Firefox, capacidades, Google Home e análise de imagens`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._