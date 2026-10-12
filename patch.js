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
