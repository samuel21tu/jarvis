# Especificação Técnica: Correção do Bug de Mudo e Loop no Microfone Mobile

## 1. Identificação do Problema
- **Sintoma Observado:** Na versão mobile do site (HUD Jarvis), ao ativar o microfone e falar, a interface/canal fica mudo; ao cessar a fala, o sistema entra em loop infinito de reconexão/reinício.
- **Ambiente Afetado:** Navegadores móveis (Android Chrome / WebKit Mobile) e WebViews embutidas em dispositivos móveis.

## 2. Diagnóstico da Causa Raiz
1. **Instabilidade do SpeechRecognition com `continuous = false` no Mobile:**
   - No mobile, o motor de fala do SO encerra a sessão e emite `onend` imediatamente após qualquer pausa vocal ou detecção de silêncio.
2. **Loop de Reinicialização Agressivo (Restart Thrashing):**
   - O handler `onend` chama `scheduleRecognitionRestart(320)`. Se o microfone não captar som ou emitir `no-speech`, o ciclo dispara repetidamente a cada 320ms sem backoff, sobrecarregando a pilha de áudio do navegador.
3. **Colisão de Recursos de Áudio no SO Móvel ("Fica Mudo"):**
   - No Android, invocar `SpeechRecognition.start()` em alta frequência enquanto o subsistema de áudio (`AudioContext` / `getUserMedia`) tenta acessar o hardware provoca a perda de foco de áudio (Audio Focus), resultando no silenciamento forçado da entrada.
4. **Ausência de Trava de Transição na FSM de Voz:**
   - Falta de controle unificado de estados mutuamente exclusivos (`IDLE`, `LISTENING`, `PROCESSING`, `SPEAKING`, `COOLDOWN`, `MUTED`), permitindo condições de corrida entre o despacho de comando (`dispatchUserVoiceCommand`), a resposta do WebSocket e a retomada do microfone.

## 3. Matriz de Entregas por Nó

### Antigravity 2 (App Linux / Nó Nativo)
- Garantir permissões de áudio no sandbox Flatpak (`--socket=pulseaudio`, acesso a PipeWire).
- Configurar permissões de microfone do WebKitGTK (`WebKitUserMediaPermissionRequest` no `jarvis_tray.py`), prevenindo que a janela embutida no Linux silencie o microfone.
- Sincronizar o estado de mute do sistema operacional (`pactl` / PipeWire) com o status do microfone do Jarvis.

### Antigravity 3 (Frontend Web / Web Audio & app.js)
- Refatorar a Máquina de Estados Finitos (FSM) de áudio em `src/mobile/app.js`.
- Implementar backoff exponencial e limite de tentativas para erros de `no-speech`.
- Isolar completamente `AudioContext` de `SpeechRecognition` no mobile.
- Trava atômica anti-colisão e anti-eco para síntese vocal (`SpeechSynthesis`).

### Antigravity 4 (Validação, QA & Testes)
- Criar suíte de testes de FSM para áudio e reconhecimento de voz.
- Simular cenários de fala com interrupção, latência do WebSocket e falha de TTS.
- Validar se o loop foi 100% mitigado em ambiente de teste automatizado.
