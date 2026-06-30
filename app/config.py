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

    ollama_timeout: int | None = None   # None = kein Timeout (für Overnight-Jobs)
    ollama_embed_timeout: int = 120     # Embeddings sind schnell, 2 Min reicht

    max_upload_size_mb: int = 50        # Max. PDF-Größe pro Upload in MB
    batch_concurrency: int = 3          # Parallele Batch-Match-Anfragen

    log_level: str = "INFO"


settings = Settings()
