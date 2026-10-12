import sys

with open("src/hub/jarvis_hub.py", "r") as f:
    content = f.read()

target1 = """                    # Áudio do servidor desativado para restaurar a voz nativa do Google no frontend.
                    audio_data = None
                    for mobile_ws in list(manager.active_mobiles.values()):"""

replacement1 = """                    # Gera áudio de alta qualidade via backend (Edge-TTS fallback garantido) para funcionar no background Headless
                    audio_data = await generate_tts_audio_base64(response_text)
                    for mobile_ws in list(manager.active_mobiles.values()):"""

target2 = """                    # Gera áudio de alta qualidade (ElevenLabs se API Key presente, fallback Edge-TTS)
                    # Áudio do servidor desativado para restaurar a voz nativa do Google no frontend.
                    audio_data = None

                    await websocket.send_json({"""

replacement2 = """                    # Gera áudio de alta qualidade (ElevenLabs se API Key presente, fallback Edge-TTS)
                    audio_data = await generate_tts_audio_base64(response_text)

                    await websocket.send_json({"""

if target1 in content and target2 in content:
    content = content.replace(target1, replacement1)
    content = content.replace(target2, replacement2)
    with open("src/hub/jarvis_hub.py", "w") as f:
        f.write(content)
    print("Sucesso! jarvis_hub.py modificado.")
else:
    print("Erro: Target não encontrado.")
