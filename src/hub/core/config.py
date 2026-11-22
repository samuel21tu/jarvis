from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    nexus_api_key: str = ""
    # Roteador de provedores de IA (ominiroute ou qualquer gateway compatível com Chat Completions).
    # Os aliases OPENROUTER_* preservam configurações antigas de deploy.
    llm_router_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_ROUTER_API_KEY", "OPENROUTER_API_KEY"),
    )
    llm_router_base_url: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_ROUTER_BASE_URL", "OPENROUTER_BASE_URL"),
    )
    llm_router_model: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_ROUTER_MODEL", "OPENROUTER_MODEL"),
    )
    llm_router_fallback_models: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_ROUTER_FALLBACK_MODELS", "OPENROUTER_FALLBACK_MODELS"),
    )
    llm_router_http_referer: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_ROUTER_HTTP_REFERER", "OPENROUTER_HTTP_REFERER"),
    )
    llm_router_x_title: str = Field(
        default="JARVIS",
        validation_alias=AliasChoices("LLM_ROUTER_X_TITLE", "OPENROUTER_X_TITLE"),
    )
    # Lista CSV opcional de hosts permitidos. Vazia = qualquer host público HTTPS.
    llm_router_allowed_hosts: str = ""
    llm_provider: str = "ominiroute"
    # Porta do Hub local. Convenção: servidor usa 8080 (padrão); o PC usa 8081 via
    # JARVIS_PORT (jarvis_tray.py faz setdefault em 8081). Não mudar sem alinhar o deploy.
    jarvis_port: int = 8080
    llm_timeout_seconds: float = 45.0
    llm_max_attempts: int = 2
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "onwK4e9ZLuTAKqWW03F9"
    # Caminho do vault do Obsidian. O servidor deve definir OBSIDIAN_VAULT_PATH próprio
    # (ex.: /data/obsidian_vault) para não herdar o caminho local do PC.
    obsidian_vault_path: str = "/home/samuel/Documentos/Programacao/jarvis/obsidian_vault"
    # Banco de memória conversacional, separado do Obsidian (que guarda só conhecimento).
    # O default é o caminho do PC; o servidor deve definir MEMORY_DB_PATH próprio
    # (ex.: /data/memory/jarvis_memory.db) para ter o próprio arquivo, sem compartilhar.
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

    def modelos_llm_router(self) -> list[str]:
        """Retorna o modelo do roteador e seus reservas na ordem declarada."""
        return _lista_csv(self.llm_router_model, self.llm_router_fallback_models)

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
