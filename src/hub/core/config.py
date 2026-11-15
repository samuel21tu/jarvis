from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    nexus_api_key: str = ""
    gemini_api_key: str = ""
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = ""
    llm_provider: str = "gemini"
    llm_timeout_seconds: float = 45.0
    llm_max_attempts: int = 2
    gemini_model: str = "gemini-flash-latest"
    gemini_fallback_models: str = "gemini-3.5-flash,gemini-flash-lite-latest,gemini-3.5-flash-lite"
    openrouter_fallback_models: str = ""
    openrouter_http_referer: str = ""
    openrouter_x_title: str = "JARVIS"
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "onwK4e9ZLuTAKqWW03F9"
    obsidian_vault_path: str = "/home/samuel/Documentos/Programacao/jarvis/obsidian_vault"
    # Banco de memória conversacional, separado do Obsidian (que guarda só conhecimento)
    memory_db_path: str = "/home/samuel/Documentos/Programacao/jarvis/data/memory/jarvis_memory.db"
    
    # Configurações do Provedor Ollama (IA Local)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_fallback_models: str = "qwen2.5-coder:7b,granite4:micro"
    ollama_timeout_seconds: float = 60.0

    # Configuração de Topologia de Rede e Papel do Nó
    nexus_url: str = "ws://192.168.1.92:8080"
    node_id: str = "cachyos_linux"
    node_role: str = "server"  # 'server' para o Hub CasaOS ou 'local' para o PC com Ollama

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def modelos_gemini(self) -> list[str]:
        """Retorna modelos Gemini configurados, sem itens vazios ou duplicados."""
        return _lista_csv(self.gemini_model, self.gemini_fallback_models)

    def modelos_openrouter(self) -> list[str]:
        """Retorna o modelo OpenRouter e seus reservas na ordem declarada."""
        return _lista_csv(self.openrouter_model, self.openrouter_fallback_models)

    def modelos_ollama(self) -> list[str]:
        """Retorna o modelo Ollama principal e seus reservas."""
        return _lista_csv(self.ollama_model, self.ollama_fallback_models)


def _lista_csv(principal: str, reservas: str) -> list[str]:
    """Normaliza uma lista CSV de modelos, preservando a primeira ocorrência."""
    resultado: list[str] = []
    for valor in f"{principal},{reservas}".split(","):
        valor = valor.strip()
        if valor and valor not in resultado:
            resultado.append(valor)
    return resultado


settings = Settings()
