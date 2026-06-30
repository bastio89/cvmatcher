import json
import logging
import os
import httpx
from fastapi import APIRouter
from pydantic import BaseModel
from app.config import settings
from app.dependencies import get_provider, get_vector_store

logger = logging.getLogger(__name__)
router = APIRouter()

_SETTINGS_FILE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "runtime_settings.json"))


class ConnectionSettings(BaseModel):
    qdrant_host: str
    qdrant_port: int
    ollama_host: str
    ollama_timeout: int | None = None
    ollama_embed_timeout: int = 120
    max_upload_size_mb: int = 50
    batch_concurrency: int = 3


@router.get("/settings", tags=["System"], summary="Verbindungseinstellungen abrufen")
async def get_settings():
    return {
        "qdrant_host": settings.qdrant_host,
        "qdrant_port": settings.qdrant_port,
        "ollama_host": settings.ollama_host,
        "ollama_timeout": settings.ollama_timeout,
        "ollama_embed_timeout": settings.ollama_embed_timeout,
        "max_upload_size_mb": settings.max_upload_size_mb,
        "batch_concurrency": settings.batch_concurrency,
    }


@router.put("/settings", tags=["System"], summary="Verbindungseinstellungen aktualisieren")
async def update_settings(body: ConnectionSettings):
    for field in body.model_fields:
        setattr(settings, field, getattr(body, field))

    get_provider.cache_clear()
    get_vector_store.cache_clear()

    with open(_SETTINGS_FILE, "w") as f:
        json.dump(body.model_dump(), f, indent=2)

    try:
        store = get_vector_store()
        await store.ensure_collection()
    except Exception as e:
        logger.warning(f"Qdrant nach Settings-Update nicht erreichbar: {e}")

    return {"status": "updated", **body.model_dump()}


@router.get("/health/services", tags=["System"], summary="Dienststatus prüfen")
async def health_services():
    qdrant_ok = False
    qdrant_error = None
    try:
        from qdrant_client import AsyncQdrantClient
        client = AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
        await client.get_collections()
        qdrant_ok = True
    except Exception as e:
        qdrant_error = str(e)[:120]

    ollama_ok = False
    ollama_error = None
    ollama_models = None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{settings.ollama_host}/api/tags")
            ollama_ok = r.status_code == 200
            if ollama_ok and settings.ai_provider == "ollama":
                available = {m["name"].split(":")[0] for m in r.json().get("models", [])}
                ollama_models = {
                    "embedding": {
                        "name": settings.embedding_model,
                        "available": settings.embedding_model in available,
                    },
                    "llm": {
                        "name": settings.llm_model,
                        "available": settings.llm_model in available,
                    },
                }
    except Exception as e:
        ollama_error = str(e)[:120]

    return {
        "qdrant": {
            "host": settings.qdrant_host,
            "port": settings.qdrant_port,
            "ok": qdrant_ok,
            "error": qdrant_error,
        },
        "ollama": {
            "host": settings.ollama_host,
            "ok": ollama_ok,
            "models": ollama_models,
            "error": ollama_error,
        },
    }
