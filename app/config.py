from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ai_provider: str = "ollama"

    ollama_host: str = "http://localhost:11434"
    embedding_model: str = "nomic-embed-text"
    llm_model: str = "llama3.2"

    anthropic_api_key: str = ""
    anthropic_embedding_model: str = "voyage-3"
    anthropic_llm_model: str = "claude-sonnet-4-6"

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    log_level: str = "INFO"


settings = Settings()
