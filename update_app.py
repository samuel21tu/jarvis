import sys

with open("src/mobile/app.js", "r") as f:
    content = f.read()

target = """function speakNextSentence() {
    clearTimeout(speakingWatchdogTimer);

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
    const utterance = new SpeechSynthesisUtterance(sentenceText);
    utterance.lang = 'pt-BR';
    utterance.rate = 1.05;
    utterance.pitch = 0.95;

    loadVoices();
    const allVoices = (synthVoices && synthVoices.length > 0) ? synthVoices : (window.speechSynthesis ? window.speechSynthesis.getVoices() : []);
    const ptVoices = allVoices.filter(v => v.lang && (v.lang.toLowerCase().includes('pt') || v.lang.toLowerCase().includes('br')));
    if (ptVoices.length > 0) {
        const googleVoice = ptVoices.find(v => v.name.includes('Google'));
        const preferred = googleVoice || ptVoices.find(v => v.name.includes('Luciana') || v.name.includes('Daniel') || v.name.includes('Francisca')) || ptVoices[0];
        utterance.voice = preferred;
    } else if (allVoices.length > 0) {
        utterance.voice = allVoices[0];
    }

    let sentenceFinished = false;

    const advanceSentence = () => {
        if (sentenceFinished) return;
        sentenceFinished = true;
        clearTimeout(speakingWatchdogTimer);
        currentSpeechIndex++;
        // Pequeno intervalo natural entre frases (120ms)
        setTimeout(() => {
            if (isAISpeaking) speakNextSentence();
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
            advanceSentence();
        }
    }, estimatedSentenceMs);

    try {
        window.speechSynthesis.speak(utterance);
    } catch (e) {
        console.warn("Falha ao invocar speak():", e);
        advanceSentence();
    }
}"""

replacement = """function speakNextSentence() {
    clearTimeout(speakingWatchdogTimer);

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
    
    if (allVoices.length === 0) {
        console.warn("Nenhuma voz local encontrada (modo headless?). Usando fallback Google Translate TTS.");
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
            setTimeout(() => {
                if (isAISpeaking) speakNextSentence();
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
        if (ptVoices.length > 0) {
            const googleVoice = ptVoices.find(v => v.name.includes('Google'));
            const preferred = googleVoice || ptVoices.find(v => v.name.includes('Luciana') || v.name.includes('Daniel') || v.name.includes('Francisca')) || ptVoices[0];
            utterance.voice = preferred;
        } else if (allVoices.length > 0) {
            utterance.voice = allVoices[0];
        }

        let sentenceFinished = false;

        const advanceSentence = () => {
            if (sentenceFinished) return;
            sentenceFinished = true;
            clearTimeout(speakingWatchdogTimer);
            currentSpeechIndex++;
            // Pequeno intervalo natural entre frases (120ms)
            setTimeout(() => {
                if (isAISpeaking) speakNextSentence();
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
}"""

if target in content:
    content = content.replace(target, replacement)
    with open("src/mobile/app.js", "w") as f:
        f.write(content)
    print("Sucesso! Código substituído.")
else:
    print("Erro: Target string não encontrada no app.js.")
