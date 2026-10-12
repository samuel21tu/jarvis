import re

with open('src/mobile/app.js', 'r') as f:
    content = f.read()

# Replace speakNextSentence logic
old_func = """function speakNextSentence() {
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
    let selectedVoice = ptVoices.find(v => v.name.includes('Google') || v.name.includes('Online')) ||
                        ptVoices.find(v => v.name.includes('Microsoft Antonio') || v.name.includes('Microsoft Daniel')) ||
                        ptVoices[0];
    
    if (selectedVoice) {
        utterance.voice = selectedVoice;
    }

    utterance.onstart = () => {
        setCoreState("speaking");
    };

    utterance.onend = () => {
        currentSpeechIndex++;
        speakNextSentence();
    };

    utterance.onerror = (e) => {
        console.warn("SpeechSynthesis erro:", e);
        currentSpeechIndex++;
        speakNextSentence();
    };

    // Watchdog de segurança
    speakingWatchdogTimer = setTimeout(() => {
        console.warn("Watchdog: Tempo limite da frase esgotado.");
        currentSpeechIndex++;
        speakNextSentence();
    }, 15000);

    try {
        window.speechSynthesis.speak(utterance);
    } catch (e) {
        console.warn("Falha no speak() síncrono:", e);
        currentSpeechIndex++;
        speakNextSentence();
    }
}"""

new_func = """function speakNextSentence() {
    clearTimeout(speakingWatchdogTimer);

    if (!isAISpeaking || currentSpeechIndex >= currentSpeechQueue.length) {
        onAISpeechFinished();
        return;
    }

    const sentenceText = currentSpeechQueue[currentSpeechIndex];
    
    const useWebSpeech = ('speechSynthesis' in window) && window.speechSynthesis.getVoices().length > 0;

    if (!useWebSpeech) {
        // Fallback para Google Translate TTS (Chrome Headless)
        const url = "https://translate.google.com/translate_tts?ie=UTF-8&q=" + encodeURIComponent(sentenceText) + "&tl=pt-BR&client=tw-ob";
        const audio = new Audio(url);
        currentAudioElement = audio;
        
        speakingWatchdogTimer = setTimeout(() => {
            console.warn("Watchdog: TTS remoto timeout.");
            currentAudioElement = null;
            currentSpeechIndex++;
            speakNextSentence();
        }, 15000);
        
        audio.onplay = () => {
            setCoreState("speaking");
        };
        
        audio.onended = () => {
            clearTimeout(speakingWatchdogTimer);
            currentAudioElement = null;
            currentSpeechIndex++;
            speakNextSentence();
        };
        
        audio.onerror = () => {
            clearTimeout(speakingWatchdogTimer);
            currentAudioElement = null;
            currentSpeechIndex++;
            speakNextSentence();
        };
        
        audio.play().catch(e => {
            console.error("Audio playback falhou:", e);
            clearTimeout(speakingWatchdogTimer);
            currentAudioElement = null;
            currentSpeechIndex++;
            speakNextSentence();
        });
        return;
    }

    // Código original WebSpeech
    try {
        if (window.speechSynthesis && window.speechSynthesis.paused) {
            window.speechSynthesis.resume();
        }
    } catch (e) {}

    const utterance = new SpeechSynthesisUtterance(sentenceText);
    utterance.lang = 'pt-BR';
    utterance.rate = 1.05;
    utterance.pitch = 0.95;

    loadVoices();
    const allVoices = (synthVoices && synthVoices.length > 0) ? synthVoices : (window.speechSynthesis ? window.speechSynthesis.getVoices() : []);
    const ptVoices = allVoices.filter(v => v.lang && (v.lang.toLowerCase().includes('pt') || v.lang.toLowerCase().includes('br')));
    let selectedVoice = ptVoices.find(v => v.name.includes('Google') || v.name.includes('Online')) ||
                        ptVoices.find(v => v.name.includes('Microsoft Antonio') || v.name.includes('Microsoft Daniel')) ||
                        ptVoices[0];
    
    if (selectedVoice) {
        utterance.voice = selectedVoice;
    }

    utterance.onstart = () => {
        setCoreState("speaking");
    };

    utterance.onend = () => {
        currentSpeechIndex++;
        speakNextSentence();
    };

    utterance.onerror = (e) => {
        console.warn("SpeechSynthesis erro:", e);
        currentSpeechIndex++;
        speakNextSentence();
    };

    speakingWatchdogTimer = setTimeout(() => {
        console.warn("Watchdog: Tempo limite da frase esgotado.");
        currentSpeechIndex++;
        speakNextSentence();
    }, 15000);

    try {
        window.speechSynthesis.speak(utterance);
    } catch (e) {
        console.warn("Falha no speak() síncrono:", e);
        currentSpeechIndex++;
        speakNextSentence();
    }
}"""

if old_func in content:
    content = content.replace(old_func, new_func)
    with open('src/mobile/app.js', 'w') as f:
        f.write(content)
    print("Patch TTS aplicado com sucesso.")
else:
    print("Bloco speakNextSentence não encontrado exatamente.")
