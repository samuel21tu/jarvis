import re

with open('/home/samuel/Documentos/Programacao/jarvis/src/mobile/app.js', 'r') as f:
    content = f.read()

# Add speakNextSentenceTimer
content = re.sub(
    r'let speakingWatchdogTimer = null;',
    r'let speakingWatchdogTimer = null;\nlet speakNextSentenceTimer = null;\nlet speechQueueSessionId = 0;',
    content
)

# Clear it in stopAISpeechAudioOnly
content = re.sub(
    r'function stopAISpeechAudioOnly\(\) \{[\s\S]*?clearTimeout\(speakingWatchdogTimer\);',
    r'function stopAISpeechAudioOnly() {\n    clearTimeout(speakingWatchdogTimer);\n    clearTimeout(speakNextSentenceTimer);\n    speechQueueSessionId++;',
    content
)

# Clear it in speakAIResponse
content = re.sub(
    r'clearTimeout\(speakingWatchdogTimer\);',
    r'clearTimeout(speakingWatchdogTimer);\n    clearTimeout(speakNextSentenceTimer);',
    content
)

with open('/home/samuel/Documentos/Programacao/jarvis/src/mobile/app.js', 'w') as f:
    f.write(content)
