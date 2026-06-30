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


@router.get("/settings", tags=["System"], summary="Verbindungseinstellungen abrufen")
async def get_settings():
    return {
        "qdrant_host": settings.qdrant_host,
        "qdrant_port": settings.qdrant_port,
        "ollama_host": settings.ollama_host,
    }


@router.put("/settings", tags=["System"], summary="Verbindungseinstellungen aktualisieren")
async def update_settings(body: ConnectionSettings):
    settings.qdrant_host = body.qdrant_host
    settings.qdrant_port = body.qdrant_port
    settings.ollama_host = body.ollama_host

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
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{settings.ollama_host}/api/tags")
            ollama_ok = r.status_code == 200
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
            "error": ollama_error,
        },
    }
