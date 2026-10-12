from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    nexus_api_key: str = ""
    gemini_api_key: str = ""
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "onwK4e9ZLuTAKqWW03F9"
    obsidian_vault_path: str = "/home/samuel/Documentos/Programacao/jarvis/obsidian_vault"
    # Banco de memória conversacional, separado do Obsidian (que guarda só conhecimento)
    memory_db_path: str = "/home/samuel/Documentos/Programacao/jarvis/data/memory/jarvis_memory.db"
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
