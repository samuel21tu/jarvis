# ADR-0001: Gestão de Ciclo de Vida do AudioContext, VAD e Desbloqueio de Hit-Test no Mobile

## Status
Aceito

## Contexto
Em dispositivos móveis (navegadores WebKit no iOS e Blink no Android), políticas rígidas de reprodução de mídia suspendem o `AudioContext` até que ocorra um gesto explícito do usuário.
Além disso, a captura contínua de áudio via microfone apresentava duas falhas críticas:
1. Períodos de silêncio disparavam mensagens vazias no WebSocket a cada 1.4s, sobrecarregando o Hub e gerando desconexões repetidas que deixavam a interface travada no estado `MUTED`.
2. A sobreposição visual do canvas do Orb 3D bloqueava os eventos de clique no botão de status, e corridas assíncronas no recebimento de áudio sintetizado (TTS) geravam a reprodução de múltiplas vozes simultâneas.

## Decisão
1. **Desbloqueio Síncrono:** Adicionar rotina `unlockAudio` no primeiro toque (`touchstart` / `click`), garantindo transição do `AudioContext` de `suspended` para `running`.
2. **Hit-Test Unificado no Orb 3D:** Vincular o evento de alternância de microfone (`handleMicToggle`) diretamente à malha interativa do Orb (`#holo-sphere-canvas` e `.holo-core-viewport`), com debounce temporal de 350ms para evitar duplo disparo (*anti-double-fire*).
3. **Guard-Rail no Backend:** Descartar imediatamente no Hub FastAPI pacotes de áudio com prompt vazio ou sem anexos (`if not prompt and not attachments: continue`), evitando requisições fantasmas.
4. **Isolamento de Voz Única:** Criar contador atômico sequencial `speakActionId` no frontend; qualquer nova resposta recebida cancela promessas de áudio anteriores e reproduz apenas o áudio mais recente.

## Consequências
- **Positivas:** Estabilidade total em dispositivos móveis, fim dos loops de reconexão causados por silêncio e eliminação da sobreposição de vozes no TTS.
- **Negativas/Mitigações:** Necessidade de manter a sincronização de classes de estado CSS entre o Orb 3D e o botão de status.
