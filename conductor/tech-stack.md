# Jarvis Nexus - Stack Tecnológica

## Servidor Central (Hub)
- **Linguagem & Runtime:** Python 3.11+ / FastAPI
- **Comunicação:** WebSockets assíncronos (`websockets`, `asyncio`)
- **Integração de IA:** Google Gemini API (padrão atual; modelos Gemini 2.5 Flash / Pro) ou OpenRouter em rollout controlado (`LLM_PROVIDER`, `OPENROUTER_BASE_URL` e `OPENROUTER_MODEL`); as chaves são fornecidas somente no ambiente de deploy
- **Armazenamento de Memória:** SQLite / JSON estruturado / Obsidian Vault integration

## Interface Cliente Mobile & HUD Web
- **Frontend Core:** HTML5, CSS3 avançado (HUD Sci-Fi / Cyberpunk), JavaScript puro (ES6+)
- **Renderização Gráfica & Áudio:**
  - Three.js para o Orbe 3D Neural
  - Web Audio API (`AudioContext`, `AnalyserNode`) para reatividade e visualizador de frequências
  - Web Speech API (`SpeechRecognition` / `webkitSpeechRecognition`, `SpeechSynthesisUtterance`)
- **Conectividade:** WebSocket nativo com reconexão automática e heartbeat

## Nós de Execução (Desktop / Nativo / Flatpak)
- **Linguagem:** Python / Shell Scripting / Flatpak
- **Comunicação:** WebSocket client bidirecional (`websockets`)
- **Telemetria de Sistema:** `psutil` (CPU, RAM, Temperatura, Uptime)
- **Pacotes e Distribuição:** Flatpak (`org.freedesktop.Platform`), systemd services

## Testes & Garantia de Qualidade
- **Testes Backend:** `pytest`, `pytest-asyncio`
- **Testes de Integração & FSM de Áudio:** Emulação de eventos WebSocket, FSM test runners e mocks de Speech APIs
