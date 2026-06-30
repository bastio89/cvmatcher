import json
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
import yaml
from app.config import settings
from app.dependencies import get_provider, get_vector_store
from app.routers import documents, matching
from app.routers.settings import router as settings_router

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

_runtime_file = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "runtime_settings.json"))
try:
    with open(_runtime_file) as _f:
        for _k, _v in json.load(_f).items():
            if hasattr(settings, _k):
                setattr(settings, _k, _v)
    logger.info(f"Runtime-Settings geladen aus {_runtime_file}")
except FileNotFoundError:
    pass
except Exception as _e:
    logger.warning(f"Fehler beim Laden der Runtime-Settings: {_e}")

_DESCRIPTION = """
## CV Matcher API

Semantisches Matching zwischen **CVs** und **Stellenbeschreibungen** — powered by lokaler KI und Vektordatenbank.

### Funktionsweise

Dokumente werden als PDF hochgeladen, der Text extrahiert (mit automatischem OCR-Fallback für Scan-PDFs)
und als Vektoren in Qdrant gespeichert. Beim Matching wird per Kosinus-Ähnlichkeit ein erster Kandidatenpool
ermittelt, der anschließend durch ein LLM detailliert analysiert und re-gerankт wird.

### Ablauf

1. **Upload** — CVs und Stellenbeschreibungen via `/api/v1/cvs/batch` oder `/api/v1/jobs/batch` hochladen
2. **ID merken** — jede Antwort enthält eine `id` pro Dokument
3. **Match starten** — `POST /api/v1/match` mit der `document_id` aufrufen
4. **Ranking auswerten** — Response enthält sortierte Treffer mit Score und LLM-Analyse

### Matching-Modi

| Quell-Typ | Ziel | Anwendungsfall |
|-----------|------|----------------|
| `cv` | Jobs | Welche Stellen passen zu diesem Bewerber? |
| `job` | CVs | Welche Kandidaten passen zu dieser Stelle? |

### KI-Provider

Aktueller Provider: wird beim Start geloggt. Lokal via Ollama oder Cloud via Anthropic/Claude.
"""

_TAGS_METADATA = [
    {
        "name": "Dokumente",
        "description": "PDF-Upload und Indexierung von CVs und Stellenbeschreibungen.",
    },
    {
        "name": "Matching",
        "description": "Semantisches Matching und Ranking zwischen CVs und Stellen.",
    },
    {
        "name": "System",
        "description": "Health-Check und API-Metadaten.",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starte CV Matcher | Provider: {settings.ai_provider}")
    try:
        store = get_vector_store()
        await store.ensure_collection()
        logger.info("Qdrant-Collection bereit")
    except Exception as e:
        logger.warning(f"Qdrant nicht erreichbar beim Start: {e} — API startet trotzdem")
    yield
    logger.info("Shutdown")


app = FastAPI(
    title="CV Matcher API",
    description=_DESCRIPTION,
    version="1.0.0",
    contact={
        "name": "CV Matcher",
    },
    license_info={
        "name": "Proprietär",
    },
    openapi_tags=_TAGS_METADATA,
    lifespan=lifespan,
)

app.include_router(documents.router, prefix="/api/v1", tags=["Dokumente"])
app.include_router(matching.router, prefix="/api/v1", tags=["Matching"])
app.include_router(settings_router, prefix="/api/v1")

_static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=_static_dir), name="static")


@app.get("/", include_in_schema=False)
async def serve_ui():
    return FileResponse(os.path.join(_static_dir, "index.html"))


@app.get("/health", tags=["System"], summary="Health-Check")
async def health():
    """Gibt den aktuellen Status der API und den konfigurierten KI-Provider zurück."""
    return {"status": "ok", "provider": settings.ai_provider}


@app.get(
    "/openapi.yaml",
    tags=["System"],
    summary="OpenAPI-Spec als YAML",
    response_class=Response,
    include_in_schema=False,
)
async def openapi_yaml():
    """Gibt die vollständige OpenAPI 3.x Spezifikation als YAML zurück (maschinenlesbar)."""
    spec = app.openapi()
    yaml_str = yaml.dump(spec, allow_unicode=True, sort_keys=False)
    return Response(content=yaml_str, media_type="application/yaml")
