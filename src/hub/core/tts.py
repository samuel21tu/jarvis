import base64
import re
import asyncio
import requests
import edge_tts
from src.hub.core.config import settings

async def _fetch_elevenlabs_audio(clean_text: str) -> bytes | None:
    def _sync_request():
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}"
        headers = {
            "xi-api-key": settings.elevenlabs_api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "text": clean_text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code == 200 and resp.content:
            return resp.content
        else:
            print(f"[TTS] ElevenLabs retornou status {resp.status_code}: {resp.text[:150]}")
            return None

    try:
        return await asyncio.to_thread(_sync_request)
    except Exception as e:
        print(f"[TTS] Exceção ao chamar ElevenLabs: {e}")
        return None

async def generate_tts_audio_base64(text: str) -> str | None:
    clean_text = re.sub(r'[*#]', '', text).strip()
    if not clean_text:
        return None
        
    audio_bytes = None
    if settings.elevenlabs_api_key:
        audio_bytes = await _fetch_elevenlabs_audio(clean_text)
    
    if not audio_bytes:
        try:
            communicate = edge_tts.Communicate(clean_text, "pt-BR-AntonioNeural")
            audio_bytes_list = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_bytes_list.append(chunk["data"])
            if audio_bytes_list:
                audio_bytes = b"".join(audio_bytes_list)
        except Exception as e:
            print(f"[TTS] Edge-TTS error: {e}")
            return None
            
    if audio_bytes:
        return base64.b64encode(audio_bytes).decode('utf-8')
    return None


