/**
 * Suíte de Testes Automatizados - FSM de Voz Mobile do Jarvis
 * Valida prevenção de loops de reinício, recuperação de silêncio e concorrência com TTS.
 */

const assert = require('assert');

// Mock da Máquina de Estados Finitos de Áudio (espelhando a lógica de app.js)
class VoiceFSM {
    constructor(isMobile = true) {
        this.isMobile = isMobile;
        this.state = 'muted'; // 'muted' | 'listening' | 'processing' | 'speaking' | 'cooldown'
        this.userIntendedMic = false;
        this.isRecognitionActive = false;
        this.isStarting = false;
        this.consecutiveSilences = 0;
        this.maxConsecutiveSilences = 3;
        this.restartCount = 0;
        this.lastDelay = 0;
        this.restartTimer = null;
        this.dispatchedCommands = [];
        this.logs = [];
    }

    log(msg) {
        this.logs.push(msg);
    }

    setCoreState(newState) {
        this.state = newState;
        this.log(`FSM State -> ${newState}`);
    }

    startRecognition() {
        if (!this.userIntendedMic) return false;
        if (this.state === 'processing' || this.state === 'speaking') return false;
        if (this.isRecognitionActive || this.isStarting) return false;

        this.isStarting = true;
        // Simulação assíncrona do start do Web Speech API
        this.isStarting = false;
        this.isRecognitionActive = true;
        this.setCoreState('listening');
        return true;
    }

    stopRecognition(abort = false) {
        if (this.restartTimer) {
            clearTimeout(this.restartTimer);
            this.restartTimer = null;
        }
        this.isRecognitionActive = false;
        this.isStarting = false;
    }

    scheduleRestart(delayMs) {
        if (!this.userIntendedMic || this.state === 'processing' || this.state === 'speaking') return;
        this.lastDelay = delayMs;
        this.restartCount++;
        // Executa imediatamente no mock de teste
        if (this.userIntendedMic && this.state !== 'processing' && this.state !== 'speaking') {
            this.startRecognition();
        }
    }

    onSpeechStart() {
        if (this.state === 'listening') {
            this.consecutiveSilences = 0;
            this.log('Fala detectada');
        }
    }

    onSpeechResult(transcript, isFinal = false) {
        if (this.state !== 'listening') return;
        this.consecutiveSilences = 0;

        if (isFinal && transcript.trim()) {
            this.dispatchCommand(transcript.trim());
        }
    }

    dispatchCommand(text) {
        this.dispatchedCommands.push(text);
        this.setCoreState('processing');
        this.stopRecognition(false);
    }

    onError(errorType) {
        this.isStarting = false;
        if (errorType === 'no-speech') {
            this.consecutiveSilences++;
            this.log(`Erro no-speech (consecutivo: ${this.consecutiveSilences})`);
        } else if (errorType === 'not-allowed') {
            this.userIntendedMic = false;
            this.stopRecognition(true);
            this.setCoreState('muted');
        }
    }

    onEnd(pendingInput = '') {
        this.isRecognitionActive = false;
        this.isStarting = false;

        if (this.userIntendedMic && this.state !== 'processing' && this.state !== 'speaking' && pendingInput.trim()) {
            this.dispatchCommand(pendingInput.trim());
            return;
        }

        if (this.userIntendedMic && this.state !== 'processing' && this.state !== 'speaking') {
            if (this.consecutiveSilences >= this.maxConsecutiveSilences) {
                this.log('Limite de silêncios atingido: pausando reinício para evitar loop.');
                this.userIntendedMic = false;
                this.setCoreState('muted');
                return;
            }

            const backoffDelay = Math.min(3000, 600 * Math.pow(1.5, this.consecutiveSilences));
            this.scheduleRestart(backoffDelay);
        } else if (this.state !== 'processing' && this.state !== 'speaking') {
            this.setCoreState('muted');
        }
    }

    onReceiveAIResponse(response) {
        this.setCoreState('speaking');
        this.stopRecognition(true);
        // Simula conclusão de TTS
    }

    onAISpeechFinished() {
        this.setCoreState('cooldown');
        if (this.userIntendedMic) {
            this.setCoreState('listening');
            this.startRecognition();
        } else {
            this.setCoreState('muted');
        }
    }
}

// Bateria de Testes
function runTests() {
    console.log("=== INICIANDO TESTES DA FSM DE ÁUDIO MOBILE ===");

    // Teste 1: Prevenção de loop infinito em silêncio consecutivo
    {
        console.log("\n[Teste 1] Validação de Proteção contra Loop Infinito (Silêncio Prolongado)...");
        const fsm = new VoiceFSM(true);
        fsm.userIntendedMic = true;
        fsm.startRecognition();
        assert.strictEqual(fsm.state, 'listening');

        // Simula 3 ciclos de no-speech seguidos de onEnd
        for (let i = 0; i < 3; i++) {
            fsm.onError('no-speech');
            fsm.onEnd();
        }

        // No 3º ciclo deve interromper o reinício automático e passar para muted
        assert.strictEqual(fsm.state, 'muted', 'FSM deveria estar em muted após limite de silêncios.');
        assert.strictEqual(fsm.userIntendedMic, false, 'userIntendedMic deve ser desativado após tolerância de silêncio.');
        console.log("-> Passou: Loop infinito mitigado com transição segura para repouso.");
    }

    // Teste 2: Ciclo de Fala -> Despacho -> Processamento -> Fala da IA -> Retomada Limpa
    {
        console.log("\n[Teste 2] Ciclo de Fala Completo e Prevenção de Mudo...");
        const fsm = new VoiceFSM(true);
        fsm.userIntendedMic = true;
        fsm.startRecognition();
        assert.strictEqual(fsm.state, 'listening');

        // Usuário fala
        fsm.onSpeechStart();
        fsm.onSpeechResult("Jarvis status do sistema", true);

        assert.strictEqual(fsm.state, 'processing', 'FSM deve transicionar para processing');
        assert.strictEqual(fsm.dispatchedCommands.length, 1);
        assert.strictEqual(fsm.isRecognitionActive, false, 'Reconhecimento deve estar pausado durante processamento');

        // Hub responde
        fsm.onReceiveAIResponse("Todos os sistemas operacionais.");
        assert.strictEqual(fsm.state, 'speaking', 'FSM deve transicionar para speaking');
        assert.strictEqual(fsm.isRecognitionActive, false, 'Reconhecimento deve permanecer inativo durante fala da IA');

        // TTS termina
        fsm.onAISpeechFinished();
        assert.strictEqual(fsm.state, 'listening', 'FSM deve retornar para listening após fala');
        assert.strictEqual(fsm.isRecognitionActive, true, 'Microfone deve reabrir sem travar');
        console.log("-> Passou: Ciclo completo executado sem travamento em mudo.");
    }

    // Teste 3: Backoff exponencial para reconexões intermediárias
    {
        console.log("\n[Teste 3] Validação de Backoff Proporcional...");
        const fsm = new VoiceFSM(true);
        fsm.userIntendedMic = true;
        fsm.startRecognition();

        // 1º erro
        fsm.onError('no-speech');
        fsm.onEnd();
        assert.strictEqual(fsm.lastDelay, 900, 'Delay no 1º silêncio deve ser 600 * 1.5 = 900ms');

        // 2º erro
        fsm.onError('no-speech');
        fsm.onEnd();
        assert.strictEqual(fsm.lastDelay, 1350, 'Delay no 2º silêncio deve ser 600 * 2.25 = 1350ms');

        console.log("-> Passou: Backoff proporcional com aumento progressivo de intervalo validado.");
    }

    console.log("\n=== TODOS OS 3 TESTES PASSARAM COM SUCESSO! ===");
}

runTests();
