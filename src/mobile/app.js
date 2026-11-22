/**
 * JARVIS NEXUS // HOLOGRAPHIC HUD CONTROLLER & 3D NEURAL CORE RENDERER
 * Interface Voice-First Sci-Fi com Esfera 3D confinada e reativa à voz (Usuário e IA).
 */

// =============================================================================
// 1. CONFIGURAÇÃO DE WEBSOCKET E ESTADO GLOBAL
// =============================================================================
// Deriva protocolo e host da própria página (LAN, CasaOS ou túnel HTTPS)
const wsProto = window.location.protocol === "https:" ? "wss" : "ws";
const wsHost = window.location.host || "127.0.0.1:8080";
const wsUrl = `${wsProto}://${wsHost}/ws/mobile/hud_${Math.floor(Math.random() * 10000)}`;
let ws = null;
let storedSessionId = localStorage.getItem("jarvis_session_id");
if (!storedSessionId) {
    storedSessionId = "session_" + Math.floor(Math.random() * 1000000);
    localStorage.setItem("jarvis_session_id", storedSessionId);
}
const sessionId = storedSessionId;

// Estados da Máquina de Voz e FSM
let isMicActive = false;
let isAISpeaking = false;
let userIntendedMicState = true; // Padrão: Microfone ativo ao iniciar
let isJarvisResting = false; // Estado de espera/descanso ativado por 'jarvis descansar'
let isProcessingCommand = false;
let isStartingRecognition = false;
let currentCoreState = "muted"; // 'muted' | 'active' | 'listening' | 'speaking' | 'processing'
let recognitionStartFailures = 0;
const MAX_START_FAILURES = 3;

// Timers de controle e prevenção de loop
let restartRecognitionTimer = null;
let speakingWatchdogTimer = null;
let speakNextSentenceTimer = null;
let speechQueueSessionId = 0;
let speechCooldownTimer = null;
let silenceDispatchTimer = null;
let commandWatchdogTimer = null;
let speechBuffer = "";
let wsReconnectTimer = null;
let wsReconnectAttempts = 0;
let lastRecognitionStartTime = 0;
let rapidRestartCount = 0;

// Níveis de áudio instantâneos (0.0 a 1.0)
let userVoiceLevel = 0.0;
let aiVoiceLevel = 0.0;

// Detecção estrita de plataforma mobile (Android/iOS)
const isMobileDevice = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);

// Web Audio API
let audioCtx = null;
let audioAnalyser = null;
let audioFreqData = null;
let mediaStreamSource = null;
let isAudioInputInitialized = false;

// Elementos da DOM
const logStream = document.getElementById('log-stream');
const cmdInput = document.getElementById('cmd-input');
const sendBtn = document.getElementById('send-btn');
const btnInterrupt = document.getElementById('btn-interrupt');
const btnMicrophone = document.getElementById('btn-microphone');
const micBtnText = document.getElementById('mic-btn-text');
const coreStateIndicator = document.getElementById('core-state-indicator');
const coreModeLabel = document.getElementById('core-mode-label');
const waveformDotsContainer = document.getElementById('waveform-dots');
const digitalClock = document.getElementById('digital-clock');
const digitalDate = document.getElementById('digital-date');

const valCpu = document.getElementById('val-cpu');
const barCpu = document.getElementById('bar-cpu');
const valRam = document.getElementById('val-ram');
const barRam = document.getElementById('bar-ram');
const valNet = document.getElementById('val-net');
const barNet = document.getElementById('bar-net');
const valGpu = document.getElementById('val-gpu');
const barGpu = document.getElementById('bar-gpu');
const valTemp = document.getElementById('val-temp');
const barTemp = document.getElementById('bar-temp');

const specUptime = document.getElementById('spec-uptime');
const specProcs = document.getElementById('spec-procs');
const specOs = document.getElementById('spec-os');

const fileDropzone = document.getElementById('file-dropzone');
const fileHiddenInput = document.getElementById('file-hidden-input');
const fileStatusLabel = document.getElementById('file-status-label');

const btnFullscreen = document.getElementById('btn-fullscreen');
const btnF11Link = document.getElementById('btn-f11-link');
const btnHelp = document.getElementById('btn-help');
const mainWorkspace = document.querySelector('.hud-main-workspace');

// Criação dinâmica dos 28 pontinhos do visualizador se não existirem
const dotElements = waveformDotsContainer.querySelectorAll('.dot');

// =============================================================================
// 2. RELÓGIO DIGITAL & TELEMETRIA TEMPORAL
// =============================================================================
function updateDigitalClock() {
    const now = new Date();
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    digitalClock.textContent = `${hours}:${minutes}:${seconds}`;

    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const dayName = days[now.getDay()];
    const dayNum = String(now.getDate()).padStart(2, '0');
    const monthName = months[now.getMonth()];
    const year = now.getFullYear();

    digitalDate.textContent = `${dayName} ${dayNum} ${monthName} ${year}`;
}
setInterval(updateDigitalClock, 1000);
updateDigitalClock();

// =============================================================================
// 3. COMUNICAÇÃO WEBSOCKET COM O JARVIS HUB (COM BACKOFF EXPONENCIAL)
// =============================================================================
function scheduleWsReconnect() {
    clearTimeout(wsReconnectTimer);
    wsReconnectAttempts++;
    // Backoff exponencial para rede móvel: 1.5s, 3s, 6s, 12s, até máx 25s + jitter
    const baseDelay = Math.min(25000, 1500 * Math.pow(1.8, Math.min(wsReconnectAttempts, 6)));
    const jitter = Math.floor(Math.random() * 800);
    const finalDelay = Math.floor(baseDelay + jitter);

    wsReconnectTimer = setTimeout(() => {
        if (!ws || ws.readyState === WebSocket.CLOSED) {
            initWebSocket();
        }
    }, finalDelay);
}

function initWebSocket() {
    // Evita duplicar conexões ativas ou em handshake
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
        return;
    }

    try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            wsReconnectAttempts = 0;
            clearTimeout(wsReconnectTimer);
            appendLogLine("SYS: Link established with Nexus Hub.", "sys");
            appendLogLine("SYS: JARVIS voice matrix ready.", "sys");
            appendLogLine("SYS: Continuous session memory active.", "sys");

            if (!isMicActive && !userIntendedMicState) {
                setCoreState("muted");
            } else if (userIntendedMicState && !isAISpeaking && !isProcessingCommand) {
                setCoreState("listening");
            }
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);

                if (data.type === "telemetry") {
                    handleTelemetry(data.nodes);
                } else if (data.type === "hardware_telemetry") {
                    updateHardwareMetrics(data.metrics);
                } else if (data.type === "log_stream") {
                    appendLogLine(`SYS: ${data.content}`, data.level || "sys");
                } else if (data.type === "chat_response") {
                    // Resposta da IA recebida: cancela watchdog de timeout
                    clearTimeout(commandWatchdogTimer);
                    appendLogLine(`JARVIS: ${data.content}`, "jarvis");
                    // Dispara a resposta em voz alta do Jarvis (passando texto e o audio_data se fornecido)
                    speakAIResponse(data.content, data.audio_data);
                }
            } catch (err) {
                console.error("Erro ao processar mensagem WS:", err);
            }
        };

        ws.onclose = () => {
            appendLogLine("SYS: Conexão com Nexus Hub oscilou. Reconectando...", "error");
            if (!userIntendedMicState) {
                setCoreState("muted");
            }
            scheduleWsReconnect();
        };

        ws.onerror = (err) => {
            console.warn("Aviso na conexão WebSocket:", err);
        };
    } catch (e) {
        console.error("Falha ao inicializar WebSocket:", e);
        scheduleWsReconnect();
    }
}

let audioUnlocked = false;
let globalSilentAudio = null;

function unlockAudio() {
    try {
        if (!audioCtx) {
            const AudioContextClass = window.AudioContext || window.webkitAudioContext;
            if (AudioContextClass) {
                audioCtx = new AudioContextClass();
            }
        }
        if (audioCtx && audioCtx.state === 'suspended') {
            audioCtx.resume().catch(() => {});
        }
        if (!globalSilentAudio) {
            globalSilentAudio = new Audio("data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQQAAAAAAA==");
        }
        globalSilentAudio.play().then(() => {
            globalSilentAudio.pause();
        }).catch(() => {});

        if ('speechSynthesis' in window) {
            try {
                if (!isAISpeaking) {
                    window.speechSynthesis.cancel();
                }
                if (window.speechSynthesis.paused) {
                    window.speechSynthesis.resume();
                }
            } catch (e) {}
        }
        audioUnlocked = true;
    } catch (e) {
        console.warn("Aviso ao liberar áudio:", e);
    }
}
document.body.addEventListener('click', unlockAudio, { passive: true });
document.body.addEventListener('touchstart', unlockAudio, { passive: true });

let hasRealTelemetry = false;

function updateHardwareMetrics(m) {
    if (!m) return;
    hasRealTelemetry = true;

    if (m.cpu !== undefined) {
        const cpuVal = Math.round(m.cpu);
        valCpu.textContent = `${cpuVal}%`;
        barCpu.style.width = `${Math.min(100, cpuVal)}%`;
    }
    if (m.ram !== undefined) {
        const ramVal = Math.round(m.ram);
        valRam.textContent = `${ramVal}%`;
        barRam.style.width = `${Math.min(100, ramVal)}%`;
    }
    if (m.temp !== undefined && m.temp !== "N/A") {
        valTemp.textContent = m.temp;
        const numTemp = parseInt(m.temp) || 45;
        barTemp.style.width = `${Math.min(100, numTemp)}%`;
    }
    if (m.uptime !== undefined) {
        specUptime.textContent = m.uptime;
    }
    if (m.procs !== undefined) {
        specProcs.textContent = m.procs;
    }
    if (m.os !== undefined) {
        specOs.textContent = m.os;
    }
}

function handleTelemetry(nodes) {
    const nodeKeys = Object.keys(nodes || {});
    if (nodeKeys.length > 0) {
        document.getElementById('chip-core').textContent = "ACTIVE";
        document.getElementById('chip-core').className = "chip-status text-green";
    } else {
        hasRealTelemetry = false;
        document.getElementById('chip-core').textContent = "STANDBY";
        document.getElementById('chip-core').className = "chip-status text-cyan";
    }
}

// Fallback de monitor para oscilação tátil caso o nó ainda não tenha transmitido
function updateMonitorMeters() {
    if (hasRealTelemetry) return; // Se temos dados reais do PC, usa os dados 100% reais!

    const baseCpu = 32 + Math.floor(Math.sin(Date.now() / 2800) * 14);
    valCpu.textContent = `${baseCpu}%`;
    barCpu.style.width = `${baseCpu}%`;

    const baseRam = 41 + Math.floor(Math.cos(Date.now() / 4200) * 3);
    valRam.textContent = `${baseRam}%`;
    barRam.style.width = `${baseRam}%`;

    const netSpeed = 485 + Math.floor(Math.random() * 55);
    valNet.textContent = `${netSpeed} KB/s`;
    barNet.style.width = `${Math.min(100, Math.floor(netSpeed / 8))}%`;

    const baseGpu = 15 + Math.floor(Math.sin(Date.now() / 2300) * 5);
    valGpu.textContent = `${baseGpu}%`;
    barGpu.style.width = `${baseGpu}%`;
}
setInterval(updateMonitorMeters, 2000);

// =============================================================================
// 4. LOG DE ATIVIDADES E CHAT
// =============================================================================
/**
 * Escapa HTML basico. Usado antes de interpolar texto em innerHTML.
 */
function escapeHtml(value) {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

/**
 * Renderiza Markdown da IA sem permitir HTML cru nem URLs perigosas.
 * marked nao sanitiza: escapar '<' antes do parse impede <img onerror>/<script>,
 * e a varredura final remove href javascript:/data: e atributos de evento.
 */
function renderSafeMarkdown(text) {
    const escaped = String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');

    const rawHtml = (typeof marked !== 'undefined')
        ? marked.parse(escaped, { breaks: true, gfm: true })
        : escaped.replace(/\n/g, '<br>');

    const template = document.createElement('template');
    template.innerHTML = rawHtml;

    template.content.querySelectorAll('*').forEach((el) => {
        Array.from(el.attributes).forEach((attr) => {
            const name = attr.name.toLowerCase();
            if (name.startsWith('on') || name === 'style' || name === 'srcdoc') {
                el.removeAttribute(attr.name);
            }
        });

        if (el.tagName === 'A') {
            const href = el.getAttribute('href') || '';
            if (/^\s*(javascript|data|vbscript):/i.test(href)) {
                el.removeAttribute('href');
            } else {
                // Todo link gerado pela IA abre em nova aba, sem window.opener
                el.setAttribute('target', '_blank');
                el.setAttribute('rel', 'noopener noreferrer');
            }
        }
    });

    return template.innerHTML;
}

function appendLogLine(text, type = "sys") {
    const line = document.createElement('div');
    line.className = `log-line ${type}`;

    if (type === "jarvis") {
        line.innerHTML = renderSafeMarkdown(text).replace(/<\/?p>/g, ' ');
    } else {
        line.textContent = text;
    }

    logStream.appendChild(line);
    logStream.scrollTop = logStream.scrollHeight;

    if (logStream.children.length > 80) {
        logStream.removeChild(logStream.firstChild);
    }
}

// =============================================================================
// 5. SISTEMA DE ÁUDIO WEB & RECONHECIMENTO DE VOZ (USUÁRIO)
// =============================================================================
let speechRecognizer = null;
let lastDispatchedPrompt = "";
let lastDispatchedTimestamp = 0;
let consecutiveSilenceErrors = 0;
const MAX_CONSECUTIVE_SILENCES = 3;

/**
 * Inicializa a captura de áudio da Web Audio API para o analisador de frequência.
 * Em dispositivos móveis (Android/iOS), não capturamos getUserMedia concorrente com o SpeechRecognition,
 * evitando que o subsistema de áudio exclusivo do SO corte ou silencie a transcrição de voz.
 * Tratado com try/catch rigoroso para nunca interromper a execução do fluxo.
 */
async function initUserAudioInput() {
    try {
        if (isMobileDevice) {
            // No celular, preservamos o canal de gravação de hardware livre para o SpeechRecognition
            return true;
        }
        if (isAudioInputInitialized && audioCtx) {
            if (audioCtx.state === 'suspended') {
                await audioCtx.resume().catch(() => {});
            }
            return true;
        }

        // Verifica existência de mediaDevices (indisponível em conexões HTTP inseguras)
        if (!navigator.mediaDevices || typeof navigator.mediaDevices.getUserMedia !== 'function') {
            console.warn("Aviso: navigator.mediaDevices.getUserMedia indisponível no ambiente atual.");
            return false;
        }

        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        if (!audioCtx && AudioContextClass) {
            audioCtx = new AudioContextClass();
        }

        if (audioCtx && audioCtx.state === 'suspended') {
            await audioCtx.resume().catch(() => {});
        }

        if (audioCtx) {
            audioAnalyser = audioCtx.createAnalyser();
            audioAnalyser.fftSize = 64;
            audioAnalyser.smoothingTimeConstant = 0.6;
            audioFreqData = new Uint8Array(audioAnalyser.frequencyBinCount);

            mediaStreamSource = audioCtx.createMediaStreamSource(stream);
            mediaStreamSource.connect(audioAnalyser);
            isAudioInputInitialized = true;
        }
        return true;
    } catch (e) {
        console.warn("Aviso: Analisador Web Audio indisponível no dispositivo:", e);
        return false;
    }
}

/**
 * Verifica se o navegador atual possui suporte para a Web Speech API.
 */
function isSpeechRecognitionSupported() {
    return !!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window);
}

/**
 * Deduplica palavras e frases consecutivas repetidas (causadas por iteração contínua da WebSpeech API).
 * Remove duplicações mesmo com diferenças de maiúsculas/minúsculas, acentos ou pontuações agregadas.
 */
function dedupeTranscript(text) {
    if (!text) return "";

    // Normaliza espaços e caracteres unicode invisíveis
    let s = text.replace(/[\u00A0\u1680\u180E\u2000-\u200B\u202F\u205F\u3000]/g, " ").trim();
    if (!s) return "";

    // 1. Remove palavras consecutivas adjacentes ignorando pontuação, caixa alta/baixa e acentos
    const rawWords = s.split(/\s+/);
    const filteredWords = [];
    let lastClean = "";

    for (let i = 0; i < rawWords.length; i++) {
        const raw = rawWords[i];
        const clean = raw.toLowerCase()
            .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
            .replace(/[^\w]/g, "");

        if (!clean || clean !== lastClean) {
            filteredWords.push(raw);
            if (clean) lastClean = clean;
        }
    }
    s = filteredWords.join(" ");

    // 2. Remove repetições consecutivas de frases ou n-gramas (de n=8 até 1)
    let prev = "";
    while (prev !== s) {
        prev = s;
        const words = s.split(/\s+/);
        const len = words.length;
        let changed = false;

        for (let n = Math.min(8, Math.floor(len / 2)); n >= 1; n--) {
            for (let i = 0; i <= len - 2 * n; i++) {
                const chunk1 = words.slice(i, i + n).map(w => w.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^\w]/g, "")).join(" ");
                const chunk2 = words.slice(i + n, i + 2 * n).map(w => w.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^\w]/g, "")).join(" ");

                if (chunk1 && chunk1 === chunk2) {
                    words.splice(i + n, n);
                    s = words.join(" ");
                    changed = true;
                    break;
                }
            }
            if (changed) break;
        }
    }

    return s.trim();
}

/**
 * Cria e configura uma nova instância de SpeechRecognition com todos os manipuladores de evento.
 */
function createSpeechRecognizer() {
    if (!isSpeechRecognitionSupported()) {
        return null;
    }

    try {
        const SpeechClass = window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognizer = new SpeechClass();
        recognizer.lang = 'pt-BR';
        // continuous: true mantém a escuta ativa entre pausas da fala
        recognizer.continuous = true;
        recognizer.interimResults = true;
        recognizer.maxAlternatives = 1;

        recognizer.onstart = () => {
            isStartingRecognition = false;
            isMicActive = true;
            recognitionStartFailures = 0;
            consecutiveSilenceErrors = 0;
            lastRecognitionStartTime = Date.now();
            updateMicUI(true);

            if (!isProcessingCommand && !isAISpeaking) {
                setCoreState("listening");
            }
        };

        recognizer.onspeechstart = () => {
            consecutiveSilenceErrors = 0;
            if (isMobileDevice && !isJarvisResting && currentCoreState !== "standby") {
                userVoiceLevel = 0.65;
            }
            // Ignora fala se a IA estiver falando (Evita que o Jarvis ouça a si mesmo e se interrompa)
            if (isAISpeaking) {
                return;
            }
        };

        recognizer.onsoundstart = () => {
            consecutiveSilenceErrors = 0;
            if (isMobileDevice && !isJarvisResting && currentCoreState !== "standby") {
                userVoiceLevel = 0.5;
            }
            // Ignora som se a IA estiver falando
            if (isAISpeaking) {
                return;
            }
        };

        recognizer.onresult = (event) => {
            consecutiveSilenceErrors = 0;
            rapidRestartCount = 0; // Fala legítima detectada, reseta contagem de reinícios

            // MODO SURDO: Se a IA estiver falando, ignoramos QUALQUER resultado capturado (Barge-in desativado)
            if (isAISpeaking) {
                return;
            }

            let finalTranscript = '';
            let interimTranscript = '';

            // event.results já contém todo o histórico de transcrições da sessão atual (0 até length-1)
            for (let i = 0; i < event.results.length; ++i) {
                const result = event.results[i];
                const transcript = result[0].transcript;
                if (result.isFinal) {
                    finalTranscript += ' ' + transcript;
                } else {
                    interimTranscript += ' ' + transcript;
                }
            }

            const cleanFinal = dedupeTranscript(finalTranscript);
            const cleanInterim = dedupeTranscript(interimTranscript);
            const fullCleanText = dedupeTranscript((cleanFinal + " " + cleanInterim).trim());

            if (isMobileDevice && !isJarvisResting && currentCoreState !== "standby") {
                userVoiceLevel = Math.min(0.95, 0.45 + (fullCleanText.length % 5) * 0.1);
            }

            if (fullCleanText) {
                if (isJarvisResting) {
                    const { hasWakeWord } = extractWakeWordCommand(fullCleanText);
                    if (!hasWakeWord) {
                        cmdInput.value = "";
                        clearTimeout(silenceDispatchTimer);
                        silenceDispatchTimer = setTimeout(() => {
                            if (isJarvisResting) {
                                dispatchUserVoiceCommand(fullCleanText);
                            }
                        }, 1000);
                        return;
                    }
                }

                cmdInput.value = fullCleanText;
                clearTimeout(silenceDispatchTimer);
                // Envia a fala após silêncio de 1.4s
                silenceDispatchTimer = setTimeout(() => {
                    if (cmdInput.value.trim().length > 1) {
                        if (isAISpeaking) {
                            stopAISpeechAudioOnly();
                        }
                        dispatchUserVoiceCommand(cmdInput.value.trim());
                    }
                }, 1400);
            }

        };


        recognizer.onerror = (event) => {
            isStartingRecognition = false;
            const err = event.error;

            // Ausência de som no microfone: normal em pausas da fala, sem penalizar o usuário
            if (err === 'no-speech') {
                return;
            }

            // Aborto intencional não é tratado como erro
            if (err === 'aborted') {
                return;
            }

            console.warn("Aviso no reconhecimento de fala:", err);

            // Permissão negada pelo usuário ou sistema (ou falha de autostart sem gesto prévio)
            if (err === 'not-allowed' || err === 'service-not-allowed') {
                isMicActive = false;
                consecutiveSilenceErrors = 0;
                recognitionStartFailures = 0;
                clearTimeout(restartRecognitionTimer);
                clearTimeout(silenceDispatchTimer);
                updateMicUI(false);
                setCoreState("muted");
                appendLogLine("SYS: Permissão de microfone negada ou aguardando interação do usuário.", "warn");
                return;
            }

            // Falhas de captura de hardware ou rede
            if (err === 'audio-capture' || err === 'network') {
                userIntendedMicState = false;
                isMicActive = false;
                clearTimeout(restartRecognitionTimer);
                clearTimeout(silenceDispatchTimer);
                updateMicUI(false);
                setCoreState("muted");
                appendLogLine(`SYS: Falha no subsistema de áudio (${err}).`, "warn");
                return;
            }
        };

        recognizer.onend = () => {
            isMicActive = false;
            isStartingRecognition = false;

            // Proteção contra loop no PC App: se o serviço de voz encerra em < 1.2s repetidamente
            const sessionDuration = Date.now() - lastRecognitionStartTime;
            if (sessionDuration < 1200) {
                rapidRestartCount++;
            } else {
                rapidRestartCount = 0;
            }

            if (rapidRestartCount >= 3) {
                console.warn("Muitos reinícios rápidos do microfone detectados. Pausando auto-restart.");
                userIntendedMicState = false;
                rapidRestartCount = 0;
                clearTimeout(silenceDispatchTimer);
                clearTimeout(restartRecognitionTimer);
                updateMicUI(false);
                setCoreState("muted");
                appendLogLine("SYS: Microfone pausado devido a instabilidade do navegador. Clique no microfone para reativar.", "warn");
                return;
            }

            // Se o usuário mantém intenção de microfone aberto e o sistema está ocioso
            if (userIntendedMicState && !isAISpeaking && !isProcessingCommand) {
                updateMicUI(true);
                setCoreState("listening");
                scheduleRecognitionRestart(600);
            } else {
                clearTimeout(silenceDispatchTimer);
                if (!isAISpeaking && !isProcessingCommand) {
                    updateMicUI(false);
                    setCoreState("muted");
                    
                    if (cmdInput.value.trim().length > 1) {
                        dispatchUserVoiceCommand(cmdInput.value.trim());
                    }
                }
            }
        };

        return recognizer;
    } catch (e) {
        console.error("Falha ao instanciar SpeechRecognition:", e);
        return null;
    }
}

/**
 * Inicialização global da Web Speech API.
 */
function setupSpeechRecognition() {
    if (!isSpeechRecognitionSupported()) {
        console.warn("Web Speech API não disponível neste navegador.");
        return;
    }
    speechRecognizer = createSpeechRecognizer();
}

/**
 * Inicia o microfone com verificações estritas de concorrência, trava atômica e proteção integral de FSM.
 * Garante que qualquer falha nunca trave a máquina de estados.
 */
function startRecognition() {
    try {
        if (!speechRecognizer) {
            speechRecognizer = createSpeechRecognizer();
        }

        if (!speechRecognizer) {
            userIntendedMicState = false;
            isStartingRecognition = false;
            isMicActive = false;
            recognitionStartFailures = 0;
            updateMicUI(false);
            setCoreState("muted");
            appendLogLine("SYS: Reconhecimento de voz indisponível neste navegador.", "warn");
            return;
        }

        if (!userIntendedMicState) return;
        if (isAISpeaking || isProcessingCommand) return;
        if (isMicActive || isStartingRecognition) return;

        clearTimeout(restartRecognitionTimer);
        isStartingRecognition = true;

        speechRecognizer.start();
    } catch (err) {
        console.warn("Aviso ao invocar speechRecognizer.start():", err);
        isStartingRecognition = false;

        // Se o erro for de estado (o navegador já considera ativo), sincroniza a FSM
        if (err.name === 'InvalidStateError' || (err.message && err.message.includes('already started'))) {
            isMicActive = true;
            recognitionStartFailures = 0;
            updateMicUI(true);
            if (!isProcessingCommand && !isAISpeaking) {
                setCoreState("listening");
            }
            return;
        }

        recognitionStartFailures++;
        if (recognitionStartFailures >= MAX_START_FAILURES) {
            console.error("Limite de falhas de inicialização do reconhecimento atingido. Recuperando FSM.");
            userIntendedMicState = false;
            isMicActive = false;
            recognitionStartFailures = 0;
            clearTimeout(restartRecognitionTimer);
            updateMicUI(false);
            setCoreState("muted");
            appendLogLine("SYS: Não foi possível ativar o microfone. Verifique as permissões do dispositivo.", "warn");

            // Descarta e recria a instância para limpar estado corrompido do navegador
            try {
                if (speechRecognizer) speechRecognizer.abort();
            } catch (e) {}
            speechRecognizer = createSpeechRecognizer();
            return;
        }

        // Tenta novamente com backoff seguro
        scheduleRecognitionRestart(800);
    }
}

/**
 * Para o microfone de forma segura com try/catch para nunca estourar exceção.
 */
function stopRecognition(abort = false) {
    clearTimeout(restartRecognitionTimer);
    clearTimeout(silenceDispatchTimer);
    if (!speechRecognizer) {
        isMicActive = false;
        isStartingRecognition = false;
        return;
    }
    try {
        if (abort) {
            speechRecognizer.abort();
        } else {
            speechRecognizer.stop();
        }
    } catch (err) {
        console.warn("Aviso ao interromper SpeechRecognition:", err);
    } finally {
        isMicActive = false;
        isStartingRecognition = false;
    }
}

/**
 * Agenda o reinício do reconhecimento com backoff proporcional para prevenir loops.
 */
function scheduleRecognitionRestart(delayMs = 600) {
    clearTimeout(restartRecognitionTimer);
    if (!userIntendedMicState || isAISpeaking || isProcessingCommand) return;

    restartRecognitionTimer = setTimeout(() => {
        if (userIntendedMicState && !isAISpeaking && !isProcessingCommand && !isMicActive && !isStartingRecognition) {
            try {
                startRecognition();
            } catch (err) {
                console.warn("Aviso ao reiniciar reconhecimento agendado:", err);
            }
        }
    }, delayMs);
}

// =============================================================================
// RECONHECIMENTO DE PALAVRAS DE ATIVAÇÃO & DESCANSO (WAKE & SLEEP WORDS)
// =============================================================================
const SLEEP_PHRASES = [
    "jarvis pode relaxar",
    "pode relaxar jarvis",
    "pode descançar jarvis",
    "pode descansar jarvis",
    "pode descançar",
    "pode descansar",
    "descança ai",
    "descansa ai",
    "descansa aí",
    "pode relaxar",
    "relaxar jarvis",
    "jarvis descansar",
    "jarvis, descansar",
    "jarvis descanse",
    "jarvis, descanse",
    "jarvis repousar",
    "jarvis, repousar",
    "jarvis stand by",
    "jarvis, stand by",
    "jarvis standby",
    "jarvis, standby",
    "jarvis durma",
    "jarvis, durma",
    "jarvis pode descansar",
    "descansar jarvis",
    "descanse jarvis"
];

const WAKE_WORDS = [
    "acorda, jarvis",
    "acorda jarvis",
    "jarvis, acorda",
    "jarvis acorda",
    "acorda ai",
    "acorda aí",
    "acorda",
    "ta ai jarvis",
    "tá ai jarvis",
    "tá aí jarvis",
    "ta ai",
    "tá ai",
    "tá aí",
    "hey jarvis",
    "ei jarvis",
    "ok jarvis",
    "okay jarvis",
    "hi jarvis",
    "jarvis"
];

function isSleepCommand(text) {
    const norm = text.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim();
    return SLEEP_PHRASES.some(phrase => norm.includes(phrase));
}

function extractWakeWordCommand(text) {
    const norm = text.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim();
    for (const wake of WAKE_WORDS) {
        const normWake = wake.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim();
        const idx = norm.indexOf(normWake);
        if (idx !== -1) {
            const afterWake = text.substring(idx + wake.length).trim();
            const cleanCommand = afterWake.replace(/^[,.\s:]+/, "").trim();
            return { hasWakeWord: true, commandText: cleanCommand };
        }
    }
    return { hasWakeWord: false, commandText: "" };
}

/**
 * Processa e envia uma fala capturada pelo microfone, com validação de palavras de ordem.
 */
function dispatchUserVoiceCommand(text) {
    const cleanText = text.trim();
    speechBuffer = "";
    if (!cleanText) return;

    const now = Date.now();
    if (cleanText === lastDispatchedPrompt && (now - lastDispatchedTimestamp) < 1800) {
        return;
    }

    // 1. Comando de Desativação / Descanso ("jarvis descansar", "pode descansar", "descansa ai", "jarvis pode relaxar", etc.)
    if (isSleepCommand(cleanText)) {
        lastDispatchedPrompt = cleanText;
        lastDispatchedTimestamp = now;
        isJarvisResting = true;
        cmdInput.value = "";
        setCoreState("standby");
        appendLogLine("SYS: JARVIS em Modo Standby (Aguardando 'Acorda' ou 'Hey Jarvis').", "warn");
        
        if (speechRecognizer) {
            try { speechRecognizer.abort(); } catch(e){}
        }

        speakAIResponse("Certamente, senhor. Entrando em modo de espera.", null);
        return;
    }

    let textToProcess = cleanText;

    // 2. Se JARVIS está em Modo de Descanso (`isJarvisResting === true`)
    if (isJarvisResting) {
        const { hasWakeWord, commandText } = extractWakeWordCommand(cleanText);

        if (!hasWakeWord) {
            // Ignora e descarta totalmente qualquer conversa secundária capturada durante o descanso
            console.log("[JARVIS STANDBY] Fala descartada por ausência da palavra de ordem:", cleanText);
            cmdInput.value = "";
            
            // NÃO interrompe o microfone para continuar escutando a palavra de ativação
            return;
        }

        // Palavra de ordem detectada! Reativa o JARVIS
        isJarvisResting = false;
        setCoreState("listening");
        appendLogLine("SYS: JARVIS reativado por palavra de ordem!", "success");

        if (speechRecognizer) {
            try { speechRecognizer.abort(); } catch(e){}
        }

        // O usuário disse a palavra de ativação ("Acorda", "Hey Jarvis")
        // O usuário pediu: "quando dizer jarvis, descançar ele vai desconsiderar tudo oq eu disser depois menos as palavras de ativaçao"
        // Então ignoramos o resto do texto dito junto com o acordar.
        lastDispatchedPrompt = cleanText;
        lastDispatchedTimestamp = now;
        cmdInput.value = "";
        speakAIResponse("Às suas ordens, senhor.", null);
        return;
    } else {
        // Se já está no Modo de Atenção Total, remove o prefixo da palavra de ordem se presente
        const { hasWakeWord, commandText } = extractWakeWordCommand(cleanText);
        if (hasWakeWord && commandText) {
            textToProcess = commandText;
        }
    }

    lastDispatchedPrompt = cleanText;
    lastDispatchedTimestamp = now;
    consecutiveSilenceErrors = 0;

    isProcessingCommand = true;
    clearTimeout(silenceDispatchTimer);
    clearTimeout(restartRecognitionTimer);

    // stopRecognition(true); removido para não cortar o microfone

    cmdInput.value = textToProcess;
    appendLogLine(`Voice Input: "${textToProcess}"`, "sys");
    sendUserCommand();
}


/**
 * Atualiza visualmente o botão do microfone com suporte aos estados ativo, inicializando e mutado.
 */
function updateMicUI(status) {
    if (status === true || status === "active") {
        btnMicrophone.className = "action-btn btn-mic active";
        micBtnText.textContent = "MICROPHONE ACTIVE";
    } else if (status === "starting") {
        btnMicrophone.className = "action-btn btn-mic starting";
        micBtnText.textContent = "INITIALIZING...";
    } else {
        btnMicrophone.className = "action-btn btn-mic muted";
        micBtnText.textContent = "MICROPHONE MUTED";
    }
}

// =============================================================================
// =============================================================================
// VINCULAÇÃO UNIVERSAL E ROBUSTA DE CLIQUE DO MICROFONE (MOUSE & TOUCH)
// =============================================================================
let lastMicClickTimestamp = 0;

/**
 * Alterna o estado do microfone aceitando TANTO clique de mouse QUANTO toque em tela,
 * independente da largura da janela (window.innerWidth), com timestamp flag contra double-fire.
 */
function handleMicToggle(e) {
    const now = Date.now();
    if (now - lastMicClickTimestamp < 350) {
        return;
    }
    lastMicClickTimestamp = now;

    const eventType = e ? (e.type || 'inline') : 'direct';
    console.log(`[JARVIS DEBUG] Microfone acionado via ${eventType} (largura: ${window.innerWidth}px)`);

    unlockAudio();

    if (!isSpeechRecognitionSupported()) {
        const msg = "Reconhecimento de voz indisponível neste navegador. Certifique-se de usar Chrome ou Safari via HTTPS.";
        alert("Aviso JARVIS: " + msg);
        userIntendedMicState = false;
        updateMicUI(false);
        setCoreState("muted");
        return;
    }

    if (userIntendedMicState) {
        userIntendedMicState = false;
        isJarvisResting = false;
        consecutiveSilenceErrors = 0;
        recognitionStartFailures = 0;
        clearTimeout(restartRecognitionTimer);
        clearTimeout(silenceDispatchTimer);
        stopRecognition(true);
        updateMicUI(false);
        setCoreState("muted");
        appendLogLine("SYS: Microfone silenciado pelo usuário.", "sys");
    } else {
        userIntendedMicState = true;
        isJarvisResting = false; // Reativa o JARVIS no clique manual do microfone
        consecutiveSilenceErrors = 0;
        recognitionStartFailures = 0;
        rapidRestartCount = 0;

        // Feedback visual imediato na tela
        updateMicUI('starting');
        setCoreState("active");
        appendLogLine("SYS: [DEBUG] Inicializando microfone...", "sys");

        // Analisador Web Audio em background (sem bloquear o reconhecimento)
        initUserAudioInput().catch(err => {
            console.warn("[JARVIS DEBUG] Aviso no analisador de áudio:", err);
        });

        // Inicia o reconhecimento de voz com tratamento seguro
        try {
            startRecognition();
            appendLogLine("SYS: Microfone ativo. Pode falar...", "sys");
        } catch (recErr) {
            console.error("[JARVIS DEBUG] Erro ao iniciar reconhecimento:", recErr);
            appendLogLine(`SYS: [ERRO] Falha ao iniciar microfone: ${recErr.message || recErr}`, "error");
            userIntendedMicState = false;
            isStartingRecognition = false;
            isMicActive = false;
            updateMicUI(false);
            setCoreState("muted");
        }
    }
}

// Vinculação de eventos para mouse ('click') e toque ('touchend') com timestamp flag contra double-fire
btnMicrophone.addEventListener('click', handleMicToggle);
btnMicrophone.addEventListener('touchend', handleMicToggle, { passive: true });

if (coreStateIndicator) {
    coreStateIndicator.addEventListener('click', handleMicToggle);
    coreStateIndicator.addEventListener('touchend', handleMicToggle, { passive: true });
}

// Vinculação do próprio ORB (viewport e canvas) para alternar o microfone (UX touch & click)
const holoViewport = document.getElementById('holo-viewport');
if (holoViewport) {
    holoViewport.addEventListener('click', handleMicToggle);
    holoViewport.addEventListener('touchend', handleMicToggle, { passive: true });
}

const holoCanvas = document.getElementById('holo-sphere-canvas');
if (holoCanvas) {
    holoCanvas.addEventListener('click', handleMicToggle);
    holoCanvas.addEventListener('touchend', handleMicToggle, { passive: true });
}

// =============================================================================
// 6. SÍNTESE DE VOZ (RESPOSTA DA IA POR VOZ)
// =============================================================================
let synthVoices = [];

function loadVoices() {
    if ('speechSynthesis' in window) {
        synthVoices = window.speechSynthesis.getVoices() || [];
    }
}
loadVoices();
if ('speechSynthesis' in window) {
    window.speechSynthesis.onvoiceschanged = loadVoices;
    setTimeout(loadVoices, 300);
    setTimeout(loadVoices, 1200);
}

function cleanTextForSpeech(text) {
    // Remove blocos de código markdown, links e formatações pesadas para pronúncia fluida
    return text
        .replace(/```[\s\S]*?```/g, "Comando executado no terminal.")
        .replace(/`([^`]+)`/g, "$1")
        .replace(/https?:\/\/\S+/g, "link")
        .replace(/[*_#~]/g, "")
        .replace(/\[([^\]]+)\]\([^\)]+\)/g, "$1")
        .trim();
}

let currentSpeechQueue = [];
let currentSpeechIndex = 0;
let currentAudioSourceNode = null;
let currentAudioElement = null;

function base64ToBlob(base64Data, contentType = 'audio/mp3') {
    try {
        const base64Clean = base64Data.replace(/^data:audio\/\w+;base64,/, "");
        const byteCharacters = atob(base64Clean);
        const sliceSize = 1024;
        const byteArrays = [];

        for (let offset = 0; offset < byteCharacters.length; offset += sliceSize) {
            const slice = byteCharacters.slice(offset, offset + sliceSize);
            const byteNumbers = new Array(slice.length);
            for (let i = 0; i < slice.length; i++) {
                byteNumbers[i] = slice.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            byteArrays.push(byteArray);
        }

        return new Blob(byteArrays, { type: contentType });
    } catch(e) {
        console.warn("Erro ao converter Base64 para Blob:", e);
        return null;
    }
}

async function playAudioBase64WebAudio(base64Data, expectedSpeakId = null) {
    if (!audioCtx) {
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        if (AudioContextClass) audioCtx = new AudioContextClass();
    }
    if (!audioCtx) throw new Error("AudioContext não suportado.");
    if (audioCtx.state === 'suspended') {
        try {
            await Promise.race([
                audioCtx.resume(),
                new Promise((_, reject) => setTimeout(() => reject(new Error("Timeout audioCtx.resume()")), 1500))
            ]);
        } catch (e) {
            throw new Error("Falha ao retomar AudioContext. Requer interação prévia do usuário.");
        }
    }

    const base64Clean = base64Data.replace(/^data:audio\/\w+;base64,/, "");
    const binaryString = window.atob(base64Clean);
    const len = binaryString.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }

    const buffer = await audioCtx.decodeAudioData(bytes.buffer);
    
    // Verificação de concorrência: se ocorreu outra requisição enquanto decodificava, cancela
    if (expectedSpeakId !== null && expectedSpeakId !== speakActionId) {
        throw new Error("Áudio WebAudio abortado por sobreposição de nova fala.");
    }

    const source = audioCtx.createBufferSource();
    source.buffer = buffer;
    source.connect(audioCtx.destination);

    return new Promise((resolve) => {
        source.onended = () => {
            currentAudioSourceNode = null;
            resolve();
        };
        currentAudioSourceNode = source;
        source.start(0);
    });
}

/**
 * Fala a resposta da IA em voz alta com leitura sequencial frase a frase,
 * evitando cortes no meio do discurso e falhas de limite de tempo do Android TTS.
 */
function stopAISpeechAudioOnly() {
    clearTimeout(speakingWatchdogTimer);
    clearTimeout(speakNextSentenceTimer);
    
    speechQueueSessionId++;
    
    if (currentAudioElement) {
        try {
            currentAudioElement.pause();
            currentAudioElement.removeAttribute('src');
        } catch(e) {}
        currentAudioElement = null;
    }
    if (currentAudioSourceNode) {
        try {
            currentAudioSourceNode.stop();
            currentAudioSourceNode.disconnect();
        } catch(e) {}
        currentAudioSourceNode = null;
    }
    try {
        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel();
        }
    } catch(e) {}
    
    isAISpeaking = false;
    aiVoiceLevel = 0.0;
}

let speakActionId = 0;

/**
 * Fala a resposta da IA em voz alta.
 * Se o servidor enviou áudio MP3 (Edge-TTS pt-BR-AntonioNeural), reproduz via HTML5 AudioElement ou WebAudio API.
 * Caso contrário, executa fallback transparente para a síntese WebSpeech do navegador.
 */
function speakAIResponse(fullText, audioData) {
    // O servidor pode enviar content/audio_data em formatos inesperados; nunca
    // deixar isso travar a FSM com isAISpeaking = true.
    const textToSpeak = typeof fullText === 'string' ? fullText : String(fullText ?? '');
    const hasServerAudio = typeof audioData === 'string' && audioData.trim() !== '';

    speakActionId++;
    const currentSpeakId = speakActionId;

    // Pausa temporariamente o microfone para evitar captar a própria voz (loop)
    stopRecognition(true);

    // Cancela completamente a fala antiga e limpa os timers/sessão
    stopAISpeechAudioOnly();

    // 1. Marca que a IA está em modo de fala
    isAISpeaking = true;
    isProcessingCommand = false;
    clearTimeout(restartRecognitionTimer);
    clearTimeout(silenceDispatchTimer);
    clearTimeout(commandWatchdogTimer);
    clearTimeout(speakingWatchdogTimer);

    setCoreState("speaking");
    appendLogLine("SYS: JARVIS transmitindo resposta vocal...", "sys");

    if (!hasServerAudio) {
        fallbackToWebSpeech(textToSpeak);
        return;
    }

    // Watchdog e resolução da promise podem ocorrer no mesmo tick: stop() no
    // watchdog dispara onended -> resolve(). Apenas um dos dois finaliza a fala.
    let speechFinalized = false;
    const finalizeOnce = () => {
        if (speechFinalized) return false;
        speechFinalized = true;
        clearTimeout(speakingWatchdogTimer);
        return true;
    };

    speakingWatchdogTimer = setTimeout(() => {
        if (currentSpeakId !== speakActionId || !isAISpeaking) return;
        if (!finalizeOnce()) return;
        console.warn("Watchdog: áudio do servidor não terminou; liberando microfone.");
        stopAISpeechAudioOnly();
        onAISpeechFinished();
    }, Math.max(10000, textToSpeak.length * 120));

    playAudioBase64WebAudio(audioData, currentSpeakId)
        .then(() => {
            if (currentSpeakId !== speakActionId) return;
            if (!finalizeOnce()) return;
            onAISpeechFinished();
        })
        .catch((err) => {
            if (currentSpeakId !== speakActionId) return; // fala mais recente já tomou o lugar
            if (!finalizeOnce()) return;
            console.warn("Falha no áudio do servidor, usando síntese local:", err);
            fallbackToWebSpeech(textToSpeak);
        });
}

function fallbackToWebSpeech(fullText) {
    const clean = cleanTextForSpeech(fullText);
    if (!clean) {
        onAISpeechFinished();
        return;
    }
    const sentences = clean.match(/[^.!?]+[.!?]+/g) || [clean];
    currentSpeechQueue = sentences.map(s => s.trim()).filter(s => s.length > 0);
    currentSpeechIndex = 0;

    if (currentSpeechQueue.length === 0) {
        onAISpeechFinished();
        return;
    }

    // try {
    //     if ('speechSynthesis' in window) {
    //         window.speechSynthesis.cancel();
    //     }
    // } catch (e) {}

    const currentSession = speechQueueSessionId;
    clearTimeout(speakNextSentenceTimer);
    speakNextSentenceTimer = setTimeout(() => speakNextSentence(currentSession), 100);
}

function speakNextSentence(sessionId) {
    if (sessionId !== undefined && sessionId !== speechQueueSessionId) {
        return;
    }
    
    clearTimeout(speakingWatchdogTimer);
    clearTimeout(speakNextSentenceTimer);

    if (!isAISpeaking || currentSpeechIndex >= currentSpeechQueue.length) {
        onAISpeechFinished();
        return;
    }

    try {
        if (window.speechSynthesis && window.speechSynthesis.paused) {
            window.speechSynthesis.resume();
        }
    } catch (e) {}

    const sentenceText = currentSpeechQueue[currentSpeechIndex];
    let utterance = null;
    
    if ('SpeechSynthesisUtterance' in window) {
        utterance = new SpeechSynthesisUtterance(sentenceText);
        utterance.lang = 'pt-BR';
        utterance.rate = 1.05;
        utterance.pitch = 0.95;
    }

    loadVoices();
    const allVoices = (synthVoices && synthVoices.length > 0) ? synthVoices : (window.speechSynthesis ? window.speechSynthesis.getVoices() : []);
    const ptVoices = allVoices.filter(v => v.lang && (v.lang.toLowerCase().includes('pt') || v.lang.toLowerCase().includes('br')));
    
    // Voz pt-BR local tem prioridade; Google TTS fica apenas como fallback
    // (modo headless, WebView sem voices ou speechSynthesis indisponível).
    const canUseLocalVoice = !!utterance && !!window.speechSynthesis && ptVoices.length > 0;

    if (!canUseLocalVoice) {
        console.warn("Nenhuma voz pt-BR local disponível; usando fallback Google Translate TTS.");
        const fallbackUrl = `https://translate.google.com/translate_tts?ie=UTF-8&q=${encodeURIComponent(sentenceText)}&tl=pt-BR&client=tw-ob`;
        
        let sentenceFinished = false;
        const advanceSentence = () => {
            if (sentenceFinished) return;
            sentenceFinished = true;
            clearTimeout(speakingWatchdogTimer);
    
            try { 
                if (typeof currentAudioElement !== 'undefined' && currentAudioElement) {
                    currentAudioElement.pause(); 
                    currentAudioElement.src = ''; 
                }
            } catch(e){}
            currentAudioElement = null;
            currentSpeechIndex++;
            speakNextSentenceTimer = setTimeout(() => {
                if (isAISpeaking) speakNextSentence(sessionId);
            }, 120);
        };

        const audio = new Audio(fallbackUrl);
        currentAudioElement = audio; // Define global
        audio.onended = () => advanceSentence();
        audio.onerror = (e) => {
            console.warn("Erro no fallback de áudio:", e);
            advanceSentence();
        };
        
        const estimatedSentenceMs = Math.max(5000, (sentenceText.length / 4) * 1000 + 4000);
        speakingWatchdogTimer = setTimeout(() => {
            if (isAISpeaking && !sentenceFinished) {
                console.warn("Watchdog: Avançando fallback TTS.");
                advanceSentence();
            }
        }, estimatedSentenceMs);
        
        audio.play().catch(e => {
            console.error("Erro ao tocar fallback TTS:", e);
            advanceSentence();
        });
        
        // Simular variação de voz pro visual
        aiVoiceLevel = 0.5;
        setTimeout(() => { aiVoiceLevel = 0.1; }, 200);
        setTimeout(() => { aiVoiceLevel = 0.0; }, 600);
        
        return;
    }

    if (utterance) {
        const googleVoice = ptVoices.find(v => v.name.includes('Google'));
        const preferred = googleVoice
            || ptVoices.find(v => /Luciana|Daniel|Francisca/i.test(v.name))
            || ptVoices[0];
        utterance.voice = preferred;

        let sentenceFinished = false;

        const advanceSentence = () => {
            if (sentenceFinished) return;
            sentenceFinished = true;
            clearTimeout(speakingWatchdogTimer);
    
            currentSpeechIndex++;
            // Pequeno intervalo natural entre frases (120ms)
            speakNextSentenceTimer = setTimeout(() => {
                if (isAISpeaking) speakNextSentence(sessionId);
            }, 120);
        };

        utterance.onend = () => {
            advanceSentence();
        };

        utterance.onerror = (err) => {
            console.warn("Aviso na frase da síntese de voz:", err);
            advanceSentence();
        };

        // Watchdog por frase: 12s + proporção por caracteres para a frase específica
        const estimatedSentenceMs = Math.max(5000, (sentenceText.length / 4) * 1000 + 4000);
        speakingWatchdogTimer = setTimeout(() => {
            if (isAISpeaking && !sentenceFinished) {
                console.warn("Watchdog: Avançando frase travada no TTS do navegador.");
                try { window.speechSynthesis.cancel(); } catch(e){}
                advanceSentence();
            }
        }, estimatedSentenceMs);

        try {
            window.speechSynthesis.speak(utterance);
        } catch (e) {
            console.warn("Falha ao invocar speak():", e);
            advanceSentence();
        }
    }
}

/**
 * Finaliza a reprodução de fala da IA e gerencia a retomada limpa do microfone com anti-eco.
 */
function onAISpeechFinished() {
    clearTimeout(speakingWatchdogTimer);
    
    isAISpeaking = false;
    aiVoiceLevel = 0.0;

    // Se o usuário não queria o microfone ligado, mantém silenciado
    if (!userIntendedMicState) {
        isMicActive = false;
        updateMicUI(false);
        setCoreState("muted");
        return;
    }

    if (isJarvisResting) {
        setCoreState("standby");
    } else {
        setCoreState("listening");
    }

    if (userIntendedMicState && !isMicActive) {
        try {
            startRecognition();
        } catch (err) {
            console.warn("Aviso ao retomar reconhecimento após resposta vocal da IA:", err);
        }
    }
}


// =============================================================================
// 7. ENVIO DE COMANDOS E CONTROLE
// =============================================================================
function sendUserCommand() {
    const text = cmdInput.value.trim();
    if (!text) return;

    // Marca como em processamento
    isProcessingCommand = true;
    appendLogLine(`You: ${text}`, "user");
    setCoreState("processing");

    // Limpa o campo de entrada
    cmdInput.value = '';

    // Watchdog de 45 segundos para destravar a FSM caso o Hub demore ou esteja gerando áudio pesado
    clearTimeout(commandWatchdogTimer);
    commandWatchdogTimer = setTimeout(() => {
        if (isProcessingCommand) {
            console.warn("Watchdog: Resposta do Hub expirou. Restaurando estado do sistema.");
            isProcessingCommand = false;
            appendLogLine("SYS: Tempo de resposta limite excedido. Pronto para novo comando.", "warn");
            if (userIntendedMicState && !isAISpeaking) {
                scheduleRecognitionRestart(400);
            } else {
                setCoreState("muted");
            }
        }
    }, 45000);

    if (ws && ws.readyState === WebSocket.OPEN) {
        const payload = {
            action: "chat",
            prompt: text,
            session_id: sessionId
        };
        if (pendingAttachments.length > 0) {
            payload.attachments = pendingAttachments;
            appendLogLine(`SYS: Transmitindo ${pendingAttachments.length} imagem/anexo(s) para o JARVIS...`, "sys");
            pendingAttachments = [];
            clearPendingAttachments();
        }
        ws.send(JSON.stringify(payload));
    } else {
        appendLogLine("SYS: Erro - Conexão com o Hub indisponível.", "error");
        clearTimeout(commandWatchdogTimer);
        isProcessingCommand = false;
        if (userIntendedMicState) {
            scheduleRecognitionRestart(500);
        } else {
            setCoreState("muted");
        }
    }
}

sendBtn.addEventListener('click', sendUserCommand);
cmdInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendUserCommand();
});

// Ação do botão INTERRUPT [ESC]
function triggerInterrupt() {
    cmdInput.value = '';
    speechBuffer = '';

    // Invalida a fala corrente ANTES de parar o áudio. O .then() de
    // playAudioBase64WebAudio dispara no onended do stop() e compara
    // currentSpeakId com speakActionId; com o id trocado ele não religa o mic.
    speakActionId++;

    clearTimeout(restartRecognitionTimer);
    clearTimeout(speakingWatchdogTimer);
    clearTimeout(speakNextSentenceTimer);
    clearTimeout(speechCooldownTimer);
    clearTimeout(silenceDispatchTimer);
    clearTimeout(commandWatchdogTimer);

    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
    }

    // Para source WebAudio e <audio> de fallback, incrementa
    // speechQueueSessionId e zera isAISpeaking/aiVoiceLevel.
    stopAISpeechAudioOnly();

    isProcessingCommand = false;
    userVoiceLevel = 0.0;

    userIntendedMicState = false;
    stopRecognition(true);
    updateMicUI(false);
    setCoreState("muted");

    appendLogLine("SYS: Interrompido pelo usuário [ESC].", "warn");
}

let lastInterruptClickTimestamp = 0;

function handleInterruptToggle(e) {
    const now = Date.now();
    if (now - lastInterruptClickTimestamp < 350) {
        return;
    }
    lastInterruptClickTimestamp = now;

    const eventType = e ? (e.type || 'inline') : 'direct';
    console.log(`[JARVIS DEBUG] Botão INTERRUPT acionado via ${eventType} (largura: ${window.innerWidth}px)!`);
    appendLogLine(`SYS: [DEBUG] Interrupção acionada (${eventType}).`, "warn");
    triggerInterrupt();
}

btnInterrupt.addEventListener('click', handleInterruptToggle);
btnInterrupt.addEventListener('touchend', handleInterruptToggle, { passive: true });

window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') triggerInterrupt();
});

function setCoreState(state) {
    currentCoreState = state;
    coreStateIndicator.className = `status-mode-pill ${state}`;
    coreModeLabel.textContent = state.toUpperCase();

    if (state === "listening" || state === "speaking" || state === "processing") {
        waveformDotsContainer.classList.add("animating");
    } else {
        waveformDotsContainer.classList.remove("animating");
    }
}

// Inicializa reconhecimento de fala
setupSpeechRecognition();

// Mantém a pílula de status clicável como botão alternativo de microfone
if (coreStateIndicator) {
    coreStateIndicator.style.cursor = 'pointer';
}

// =============================================================================
// 8. UPLOAD DE ARQUIVOS (DRAG & DROP, PASTE E VISÃO MULTIMODAL)
// =============================================================================
let pendingAttachments = [];

fileDropzone.addEventListener('click', () => {
    fileHiddenInput.click();
});

fileHiddenInput.addEventListener('change', (e) => {
    handleSelectedFiles(e.target.files);
    e.target.value = '';
});

fileDropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    fileDropzone.classList.add('drag-over');
});

fileDropzone.addEventListener('dragleave', () => {
    fileDropzone.classList.remove('drag-over');
});

fileDropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    fileDropzone.classList.remove('drag-over');
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleSelectedFiles(e.dataTransfer.files);
    }
});

// Suporte a colar imagem (Ctrl+V) em qualquer lugar da tela
document.addEventListener('paste', (e) => {
    if (e.clipboardData && e.clipboardData.items) {
        const items = e.clipboardData.items;
        const pastedFiles = [];
        for (let i = 0; i < items.length; i++) {
            if (items[i].type.indexOf('image') !== -1) {
                const blob = items[i].getAsFile();
                if (blob) {
                    pastedFiles.push(new File([blob], `imagem_clipboard_${Date.now()}.png`, { type: blob.type }));
                }
            }
        }
        if (pastedFiles.length > 0) {
            handleSelectedFiles(pastedFiles);
            appendLogLine("SYS: Imagem colada do clipboard (Ctrl+V).", "sys");
        }
    }
});

function handleSelectedFiles(files) {
    if (!files || files.length === 0) return;
    Array.from(files).forEach((file) => {
        const reader = new FileReader();
        reader.onload = (ev) => {
            pendingAttachments.push({
                name: file.name,
                mime_type: file.type || "image/png",
                data: ev.target.result
            });
            updateFileStatusUI();
        };
        reader.readAsDataURL(file);
    });
}

function updateFileStatusUI() {
    if (pendingAttachments.length === 0) {
        fileStatusLabel.textContent = "Nenhum arquivo recarregado - arraste, clique ou cole (Ctrl+V) imagens";
    } else {
        const names = pendingAttachments.map(a => a.name).join(", ");
        const safeNames = escapeHtml(names);
        fileStatusLabel.innerHTML = `<span style="color: var(--cyan-neon); font-weight: bold;">Anexado (${pendingAttachments.length}): ${safeNames}</span> <button id="btn-clear-attachments" style="background:rgba(255,0,85,0.2);border:1px solid #ff0055;color:#ff0055;border-radius:3px;cursor:pointer;font-size:0.6rem;padding:2px 6px;margin-left:6px;">× Remover</button>`;
        const btnClear = document.getElementById('btn-clear-attachments');
        if (btnClear) {
            btnClear.onclick = (e) => {
                e.stopPropagation();
                clearPendingAttachments();
            };
        }
        appendLogLine(`SYS: Imagem/Anexo pronto para o JARVIS ler: ${names}`, "sys");
    }
}

function clearPendingAttachments() {
    pendingAttachments = [];
    fileStatusLabel.textContent = "Nenhum arquivo recarregado - arraste, clique ou cole (Ctrl+V) imagens";
}

// =============================================================================
// 9. CONTROLES DE TELA CHEIA E AJUDA
// =============================================================================
function toggleFullscreen() {
    if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(err => {
            console.warn("Falha ao entrar em tela cheia:", err);
        });
    } else {
        if (document.exitFullscreen) {
            document.exitFullscreen();
        }
    }
}

if (isMobileDevice) {
    mainWorkspace.classList.add('mobile-collapsed');
    btnFullscreen.innerHTML = `<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
        <path d="M4 6h16v2H4zm0 5h16v2H4zm0 5h16v2H4z"></path>
    </svg>`;
    btnFullscreen.title = "Expandir/Recolher Painéis";
    
    btnFullscreen.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        mainWorkspace.classList.toggle('mobile-collapsed');
    });
} else {
    btnFullscreen.addEventListener('click', toggleFullscreen);
}
btnF11Link.addEventListener('click', toggleFullscreen);

btnHelp.addEventListener('click', () => {
    appendLogLine("SYS: === JARVIS VOICE-FIRST HUD ===", "sys");
    appendLogLine("SYS: • Clique em 'MICROPHONE MUTED' para habilitar diálogo contínuo por voz.", "sys");
    appendLogLine("SYS: • Fale normalmente: o Jarvis responderá em áudio e reabrirá o microfone.", "sys");
    appendLogLine("SYS: • O orbe central reage em tempo real tanto à sua voz quanto à da IA.", "sys");
    appendLogLine("SYS: • Pressione ESC ou o botão INTERRUPT para silenciar a qualquer momento.", "sys");
});

// =============================================================================
// 10. RENDERIZADOR 3D: ESFERA HOLOGRÁFICA COM PARTÍCULAS ESTRITAMENTE CONTIDAS
//     E REATIVAS À VOZ (USUÁRIO E IA)
// =============================================================================
const canvas = document.getElementById('holo-sphere-canvas');
const ctx = canvas.getContext('2d');

let width = canvas.width = canvas.offsetWidth;
let height = canvas.height = canvas.offsetHeight;

function resizeCanvas() {
    if (!canvas.parentElement) return;
    const newWidth = canvas.parentElement.offsetWidth;
    const newHeight = canvas.parentElement.offsetHeight;
    if (newWidth > 0 && newHeight > 0) {
        width = canvas.width = newWidth;
        height = canvas.height = newHeight;
    }
}
window.addEventListener('resize', resizeCanvas);
setTimeout(resizeCanvas, 100);

if (canvas.parentElement) {
    const observer = new ResizeObserver(resizeCanvas);
    observer.observe(canvas.parentElement);
}

let rotationX = 0.2;
let rotationY = 0;

let targetRotationX = 0.2;
let targetRotationY = 0;

// Parallax com o mouse
window.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left - width / 2;
    const mouseY = e.clientY - rect.top - height / 2;
    targetRotationY = (mouseX / width) * 0.7;
    targetRotationX = -(mouseY / height) * 0.7 + 0.2;
});

// NÓS DA SUPERFÍCIE DA ESFERA (Fibonacci Sphere - Casca Externa)
const numNodes = 75;
const sphereSurfaceNodes = [];
const goldenRatio = (1 + Math.sqrt(5)) / 2;

for (let i = 0; i < numNodes; i++) {
    const theta = 2 * Math.PI * i / goldenRatio;
    const phi = Math.acos(1 - 2 * (i + 0.5) / numNodes);
    sphereSurfaceNodes.push({
        baseX: Math.cos(theta) * Math.sin(phi),
        baseY: Math.sin(theta) * Math.sin(phi),
        baseZ: Math.cos(phi),
        size: 1 + Math.random() * 1.5,
        phase: Math.random() * Math.PI * 2
    });
}

// PARTÍCULAS INTERNAS ESTRITAMENTE CONTIDAS DENTRO DA ESFERA (r <= R)
// Modeladas em coordenadas esféricas (raio, theta, phi) para garantia matemática de contenção
const numContainedParticles = 90;
const containedParticles = [];

for (let i = 0; i < numContainedParticles; i++) {
    containedParticles.push({
        // Raio varia do núcleo até 94% do raio total da esfera
        radiusRatio: 0.15 + Math.random() * 0.78,
        theta: Math.random() * Math.PI * 2,
        phi: Math.acos((Math.random() * 2) - 1),
        speedTheta: (Math.random() - 0.5) * 0.02,
        speedPhi: (Math.random() - 0.5) * 0.015,
        pulseOffset: Math.random() * Math.PI * 2,
        size: 1.0 + Math.random() * 1.6
    });
}

// Anéis Orbitais com inclinações estelares
const orbitalRings = [
    { radiusRatio: 1.0, tiltX: 0.35, tiltY: 0.1, speed: 0.005, dash: [8, 4, 16, 4] },
    { radiusRatio: 0.93, tiltX: -0.4, tiltY: 0.5, speed: -0.007, dash: [4, 12, 4, 4] },
    { radiusRatio: 0.86, tiltX: 0.8, tiltY: -0.2, speed: 0.009, dash: [14, 6] },
    { radiusRatio: 0.72, tiltX: -0.7, tiltY: -0.6, speed: -0.006, dash: [20, 8, 4, 8] },
    { radiusRatio: 0.52, tiltX: 0.1, tiltY: 0.9, speed: 0.013, dash: [6, 6] }
];

// Projeção 3D com perspectiva
function project3D(x, y, z, fov = 350) {
    const scale = fov / (fov + z);
    return {
        x: x * scale + width / 2,
        y: y * scale + height / 2,
        scale: scale
    };
}

// Rotação 3D por matriz de Euler
function rotate3D(point, rotX, rotY) {
    // Y
    const x1 = point.x * Math.cos(rotY) + point.z * Math.sin(rotY);
    const y1 = point.y;
    const z1 = -point.x * Math.sin(rotY) + point.z * Math.cos(rotY);

    // X
    const x2 = x1;
    const y2 = y1 * Math.cos(rotX) - z1 * Math.sin(rotX);
    const z2 = y1 * Math.sin(rotX) + z1 * Math.cos(rotX);

    return { x: x2, y: y2, z: z2 };
}

let animTime = 0;

// Loop principal de renderização do Núcleo Holográfico
function renderHoloCore() {
    requestAnimationFrame(renderHoloCore);
    if (width === 0 || height === 0) return;

    animTime += 0.016;

    // 1. CAPTURA E SUAVIZAÇÃO DOS NÍVEIS DE VOZ (USUÁRIO E IA)
    if (isMicActive && audioAnalyser && audioFreqData) {
        audioAnalyser.getByteFrequencyData(audioFreqData);

        if (isJarvisResting || currentCoreState === "standby") {
            // Em Standby, o Orb NÃO reage a ruídos ou vozes (comporta-se como microfone desligado)
            userVoiceLevel = userVoiceLevel * 0.8;
        } else {
            // Calcula a média das frequências de fala (bandas 2 a 20)
            let sum = 0;
            const count = 18;
            for (let i = 2; i < 2 + count; i++) {
                sum += audioFreqData[i];
            }
            const rawVol = (sum / count) / 255;
            // Suavização do nível do usuário
            userVoiceLevel = userVoiceLevel * 0.7 + rawVol * 0.3;
        }
    } else if (isMicActive && currentCoreState === "listening" && !isJarvisResting) {
        // No mobile sem conflito de Web Audio, simula pulsação orgânica sutil apenas quando ativo
        const voicePulse = (Math.sin(animTime * 11) * 0.12 + Math.sin(animTime * 17) * 0.08);
        userVoiceLevel = Math.max(userVoiceLevel * 0.88, 0.10 + voicePulse);
    } else {
        userVoiceLevel = userVoiceLevel * 0.8;
    }

    if (isAISpeaking) {
        // Modulação vocal rítmica para a fala do Jarvis
        const aiRhythm = (Math.sin(animTime * 14) * 0.4 + Math.sin(animTime * 22) * 0.3 + 0.3);
        aiVoiceLevel = Math.max(0.15, Math.min(0.95, aiRhythm * 0.85));
    } else {
        aiVoiceLevel = aiVoiceLevel * 0.8;
    }

    // Energia de voz total combinada (0.0 a 1.0)
    const combinedVoiceEnergy = Math.max(userVoiceLevel, aiVoiceLevel);

    // Raio adaptativo que respeita as dimensões do mobile para nunca cortar a esfera
    const isCollapsed = document.querySelector('.hud-main-workspace')?.classList.contains('mobile-collapsed');
    const maxMobileRadius = isCollapsed ? 210 : 145;
    const adaptiveBaseRadius = isMobileDevice 
        ? Math.min(width * 0.42, height * 0.42, maxMobileRadius) 
        : 155;
    const pulseFactor = Math.sin(animTime * 4) * 2;
    const currentRadius = adaptiveBaseRadius * (1 + combinedVoiceEnergy * 0.28) + pulseFactor;

    // Atualização visual dos 28 pontinhos (Waveform Dots)
    if (dotElements && dotElements.length > 0) {
        dotElements.forEach((dot, idx) => {
            let dotScale = 1.0;
            if (combinedVoiceEnergy > 0.04) {
                // Se for voz do usuário com analisador real
                if (userVoiceLevel > aiVoiceLevel && audioFreqData) {
                    const freqIdx = Math.floor((idx / dotElements.length) * (audioFreqData.length / 2));
                    const bandVal = (audioFreqData[freqIdx] || 0) / 255;
                    dotScale = 1.0 + bandVal * 4.2;
                } else {
                    // Modulação procedural elegante
                    const waveMod = Math.abs(Math.sin(animTime * 10 + idx * 0.35));
                    dotScale = 1.0 + (waveMod * combinedVoiceEnergy * 4.5);
                }
            }
            dot.style.transform = `scaleY(${dotScale.toFixed(2)})`;
        });
    }

    // Suavização de rotação com aceleração responsiva à voz
    const speedBoost = 1.0 + (combinedVoiceEnergy * 2.5);
    rotationX += (targetRotationX - rotationX) * 0.05;
    rotationY += 0.0035 * speedBoost + (targetRotationY - rotationY) * 0.05;

    ctx.clearRect(0, 0, width, height);

    // 2. RENDERIZA ANÉIS ORBITAIS (CASCA EXTERNA DE CONTENÇÃO)
    orbitalRings.forEach(ring => {
        const ringTime = animTime * ring.speed * 8 * speedBoost;
        const totalPoints = 64;
        const projectedPoints = [];
        const ringRadius = currentRadius * ring.radiusRatio;

        for (let i = 0; i <= totalPoints; i++) {
            const angle = (i / totalPoints) * Math.PI * 2;
            const rx = Math.cos(angle) * ringRadius;
            const ry = Math.sin(angle) * ringRadius;
            const rz = 0;

            const ringPoint = rotate3D({ x: rx, y: ry, z: rz }, ring.tiltX, ring.tiltY + ringTime);
            const rotated = rotate3D(ringPoint, rotationX, rotationY);
            projectedPoints.push(project3D(rotated.x, rotated.y, rotated.z));
        }

        ctx.beginPath();
        ctx.setLineDash(ring.dash);
        const alpha = Math.min(0.85, 0.2 + combinedVoiceEnergy * 0.55);
        ctx.strokeStyle = (isAISpeaking || userVoiceLevel > 0.08) 
            ? `rgba(0, 243, 255, ${alpha})` 
            : `rgba(0, 212, 255, ${alpha * 0.8})`;
        ctx.lineWidth = 1 + combinedVoiceEnergy * 0.8;

        for (let i = 0; i < projectedPoints.length; i++) {
            const pt = projectedPoints[i];
            if (i === 0) ctx.moveTo(pt.x, pt.y);
            else ctx.lineTo(pt.x, pt.y);
        }
        ctx.stroke();
        ctx.setLineDash([]);
    });

    // 3. RENDERIZA NÓS E CONEXÕES DA SUPERFÍCIE DA ESFERA
    const projectedSurfaceNodes = sphereSurfaceNodes.map(node => {
        const vibration = Math.sin(animTime * 12 + node.phase) * (combinedVoiceEnergy * 8);
        const r = currentRadius + vibration;
        const rotated = rotate3D({
            x: node.baseX * r,
            y: node.baseY * r,
            z: node.baseZ * r
        }, rotationX, rotationY);

        return {
            proj: project3D(rotated.x, rotated.y, rotated.z),
            z: rotated.z,
            node: node
        };
    });

    // Conexões de rede geométrica HUD na casca
    ctx.lineWidth = 0.5;
    for (let i = 0; i < projectedSurfaceNodes.length; i++) {
        for (let j = i + 1; j < projectedSurfaceNodes.length; j++) {
            const n1 = projectedSurfaceNodes[i];
            const n2 = projectedSurfaceNodes[j];
            const dx = n1.proj.x - n2.proj.x;
            const dy = n1.proj.y - n2.proj.y;
            const dist = Math.sqrt(dx * dx + dy * dy);

            if (dist < 44 && (n1.z < 60 || n2.z < 60)) {
                const connAlpha = (1 - dist / 44) * (0.2 + combinedVoiceEnergy * 0.4);
                ctx.strokeStyle = `rgba(0, 212, 255, ${connAlpha})`;
                ctx.beginPath();
                ctx.moveTo(n1.proj.x, n1.proj.y);
                ctx.lineTo(n2.proj.x, n2.proj.y);
                ctx.stroke();
            }
        }
    }

    // Desenha nós da superfície
    projectedSurfaceNodes.forEach(item => {
        if (item.z < 120) {
            const depthAlpha = Math.max(0.15, (1 - item.z / currentRadius) * 0.85);
            ctx.fillStyle = (combinedVoiceEnergy > 0.08)
                ? `rgba(255, 255, 255, ${depthAlpha})`
                : `rgba(0, 240, 255, ${depthAlpha})`;
            ctx.beginPath();
            ctx.arc(item.proj.x, item.proj.y, item.node.size * item.proj.scale, 0, Math.PI * 2);
            ctx.fill();
        }
    });

    // 4. RENDERIZA PARTÍCULAS ESTRITAMENTE CONTIDAS NO INTERIOR DA ESFERA
    containedParticles.forEach(p => {
        // Atualiza ângulos orbitais internos com aceleração por voz
        p.theta += p.speedTheta * speedBoost;
        p.phi += p.speedPhi * speedBoost;

        // O raio da partícula é mantido ESTRITAMENTE dentro de currentRadius (r <= currentRadius * 0.95)
        const innerRadius = (currentRadius * p.radiusRatio) + (Math.sin(animTime * 8 + p.pulseOffset) * (combinedVoiceEnergy * 10));
        
        // Coordenadas esféricas puras
        const px = innerRadius * Math.sin(p.phi) * Math.cos(p.theta);
        const py = innerRadius * Math.sin(p.phi) * Math.sin(p.theta);
        const pz = innerRadius * Math.cos(p.phi);

        const rotated = rotate3D({ x: px, y: py, z: pz }, rotationX, rotationY);
        const proj = project3D(rotated.x, rotated.y, rotated.z);

        const particleAlpha = Math.max(0.2, (1 - rotated.z / currentRadius) * (0.55 + combinedVoiceEnergy * 0.45));
        
        ctx.fillStyle = (combinedVoiceEnergy > 0.15) 
            ? `rgba(180, 255, 255, ${particleAlpha})` 
            : `rgba(0, 212, 255, ${particleAlpha})`;

        ctx.beginPath();
        ctx.arc(proj.x, proj.y, p.size * proj.scale * (1 + combinedVoiceEnergy * 0.5), 0, Math.PI * 2);
        ctx.fill();
    });

    // 5. NÚCLEO CENTRAL HOLOGRÁFICO RADIATIVO (REATOR DE ARCO // ARC CORE)
    const coreCenterX = width / 2;
    const coreCenterY = height / 2;
    const corePulse = Math.sin(animTime * 6) * 3;
    const coreBaseRadius = 26 + (combinedVoiceEnergy * 24) + corePulse;

    // Brilho volumétrico central expansivo quando há voz ativa
    const glowGradient = ctx.createRadialGradient(
        coreCenterX, coreCenterY, 2,
        coreCenterX, coreCenterY, coreBaseRadius * 2.4
    );
    glowGradient.addColorStop(0, "rgba(255, 255, 255, 0.98)");
    glowGradient.addColorStop(0.25, (isAISpeaking || userVoiceLevel > 0.1) ? "rgba(0, 255, 220, 0.85)" : "rgba(0, 240, 255, 0.7)");
    glowGradient.addColorStop(0.65, "rgba(0, 180, 255, 0.25)");
    glowGradient.addColorStop(1, "transparent");

    ctx.fillStyle = glowGradient;
    ctx.beginPath();
    ctx.arc(coreCenterX, coreCenterY, coreBaseRadius * 2.4, 0, Math.PI * 2);
    ctx.fill();

    // Anéis Atômicos Cruzados em rotação rápida no núcleo
    ctx.lineWidth = 1.3 + (combinedVoiceEnergy * 1.2);
    ctx.strokeStyle = (combinedVoiceEnergy > 0.08) ? "rgba(0, 255, 220, 0.9)" : "rgba(0, 240, 255, 0.85)";

    for (let i = 0; i < 3; i++) {
        const atomAngle = animTime * (1.8 + i * 0.9) * speedBoost * (i % 2 === 0 ? 1 : -1);
        ctx.save();
        ctx.translate(coreCenterX, coreCenterY);
        ctx.rotate((Math.PI / 3) * i + animTime * 0.3);
        ctx.scale(1, Math.cos(atomAngle) * 0.5 + 0.5);
        ctx.beginPath();
        ctx.arc(0, 0, coreBaseRadius, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();
    }
}

// Inicia conexão e renderizador 3D
initWebSocket();
renderHoloCore();


// =============================================================================
// AUTOSTART & VINCULAÇÃO DE GESTO DO USUÁRIO PARA ATIVAÇÃO DE MICROFONE
// =============================================================================
const urlParams = new URLSearchParams(window.location.search);
if (urlParams.has('autostart')) {
    try {
        urlParams.delete('autostart');
        const cleanQuery = urlParams.toString();
        const cleanUrl = window.location.pathname + (cleanQuery ? `?${cleanQuery}` : '') + window.location.hash;
        window.history.replaceState(null, '', cleanUrl);
    } catch (err) {
        console.warn("[JARVIS DEBUG] Não foi possível limpar a URL:", err);
    }
}

let userHasInteracted = false;
function handleFirstUserGesture() {
    unlockAudio();
    if (!userHasInteracted) {
        userHasInteracted = true;
        if (userIntendedMicState && !isMicActive && !isStartingRecognition && !isAISpeaking && !isProcessingCommand) {
            console.log("[JARVIS] Interação do usuário detectada. Ativando microfone em contexto permitido.");
            try {
                startRecognition();
            } catch (e) {
                console.warn("Aviso ao ativar microfone na primeira interação:", e);
            }
        }
    }
}

// Registra ouvintes em eventos globais de interação do usuário
window.addEventListener('click', handleFirstUserGesture);
window.addEventListener('touchstart', handleFirstUserGesture);
window.addEventListener('keydown', handleFirstUserGesture);

// Tentativa de autostart preventivo
setTimeout(() => {
    if (userIntendedMicState && !isMicActive && !isStartingRecognition) {
        console.log("[JARVIS] Tentativa inicial de ativação do microfone.");
        try {
            startRecognition();
        } catch (e) {}
    }
}, 500);

