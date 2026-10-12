# Plano de Implementação: Correção do Bug de Mudo e Loop no Microfone Mobile

## Fase 1: Diagnóstico e Cenários de Teste (Antigravity 4)
- [x] **Tarefa 1.1:** Criar mock da Web Speech API (`SpeechRecognition` e `SpeechSynthesis`) para simular o ciclo móvel de eventos (`onstart`, `onspeechstart`, `onresult`, `onend`, `onerror`).
- [x] **Tarefa 1.2:** Implementar teste de reprodução do loop de restart com `no-speech` cascateado.
- [x] **Tarefa 1.3:** Implementar teste de concorrência entre recebimento de resposta via WebSocket e estado do microfone.

## Fase 2: Implementação da FSM e Correção no Frontend Web (Antigravity 3)
- [x] **Tarefa 2.1:** Implementar FSM estrita em `src/mobile/app.js` com estados `MUTED`, `LISTENING`, `PROCESSING`, `SPEAKING`, `COOLDOWN`.
- [x] **Tarefa 2.2:** Adicionar backoff adaptativo com limite de tentativas no `scheduleRecognitionRestart` (evitando cascata de 320ms).
- [x] **Tarefa 2.3:** Garantir proteção atômica contra reinicialização simultânea de `SpeechRecognition` enquanto o WebSocket processa ou o TTS fala.
- [x] **Tarefa 2.4:** Desacoplar Web Audio API de entrada no mobile para liberar o hardware exclusivamente ao reconhecimento de voz.

## Fase 3: Permissões de Áudio e Integração no App Linux (Antigravity 2)
- [x] **Tarefa 3.1:** Adicionar permissão de áudio (`--socket=pulseaudio`) ao manifesto Flatpak `com.jarvis.Node.json`.
- [x] **Tarefa 3.2:** Implementar handler de permissão de microfone em WebKitGTK (`jarvis_tray.py`) para concessão automática de `WebKitUserMediaPermissionRequest`.
- [x] **Tarefa 3.3:** Sincronizar o estado de alternância do microfone (`pactl set-source-mute`) com o status da HUD.

## Fase 4: Integração, Execução de Testes e Aprovação (Conductor & Antigravity 4)
- [x] **Tarefa 4.1:** Executar suite completa de testes de FSM e WebSocket (`tests/test_mobile_voice_fsm.js`).
- [x] **Tarefa 4.2:** Validação cruzada e homologação final pelo Conductor.
