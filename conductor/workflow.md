# Jarvis Nexus - Fluxo de Trabalho & Governança (Conductor)

## Papéis e Governança Multi-Agente
1. **Conductor (Orquestrador Central):**
   - Planejamento, decomposição de tarefas e garantia de coesão arquitetural.
   - Validação de contratos de dados, interfaces e aprovação final de merges.
2. **Antigravity 2 (Nó da Aplicação Linux / Nativa):**
   - Focado no cliente Linux desktop (`src/node/`), Flatpak (`com.jarvis.Node.json`), tray GTK (`jarvis_tray.py`), áudio do sistema (PipeWire/PulseAudio via `pactl`), WebKitGTK e execução de comandos do sistema operacional.
3. **Antigravity 3 (Nó do Site / Frontend Web):**
   - Focado na HUD web, renderização Three.js, Web Audio API, Web Speech API e WebSocket client.
4. **Antigravity 4 (Nó de Testes / Validação & QA):**
   - Focado em suites de teste, reprodução de cenários de erro, simulação de estresse e benchmarking.

## Protocolo de Resolução de Bugs (TDD & Verificação Estrita)
1. **Reprodução:** Antigravity 4 isola o bug em cenário de teste determinístico antes da correção.
2. **Implementação:** Antigravity 2 e Antigravity 3 desenvolvem as correções em seus respectivos domínios.
3. **Validação Cruzada:** Execução dos testes automatizados e aprovação formal pelo Antigravity 4.
4. **Merge & Liberação:** Conductor valida integridade do sistema completo.
