import hashlib
import logging
import uuid
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from app.config import settings

_CONNECTION_ERRORS = (httpx.ConnectError, httpx.ConnectTimeout, ConnectionRefusedError)
_SERVICE_DOWN = "Dienst nicht erreichbar — bitte Qdrant-Status prüfen"
from app.models.schemas import (
    BatchUploadResponse,
    DeleteResponse,
    DocumentDetail,
    DocumentListItem,
    DocumentListResponse,
    DocumentType,
    UploadedDocument,
)
from app.providers.base import AIProvider
from app.services.pdf_extractor import extract_text_from_pdf
from app.services.vector_store import VectorStore
from app.dependencies import get_provider, get_vector_store

logger = logging.getLogger(__name__)
router = APIRouter()

_PDF_MAGIC = b"%PDF"


def _validate_upload(filename: str, data: bytes) -> str | None:
    """Gibt eine Fehlermeldung zurück wenn die Datei ungültig ist, sonst None."""
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(data) > max_bytes:
        mb = len(data) / 1024 / 1024
        return f"{filename}: Datei zu groß ({mb:.1f} MB, max {settings.max_upload_size_mb} MB)"
    if not data.startswith(_PDF_MAGIC):
        return f"{filename}: keine gültige PDF-Datei (falscher Dateiheader)"
    return None


async def _ingest_pdfs(
    files: list[UploadFile],
    doc_type: DocumentType,
    provider: AIProvider,
    store: VectorStore,
) -> BatchUploadResponse:
    uploaded = []
    failed = []

    for file in files:
        if not file.filename.lower().endswith(".pdf"):
            failed.append(f"{file.filename}: nur PDF erlaubt")
            continue
        try:
            pdf_bytes = await file.read()

            error = _validate_upload(file.filename, pdf_bytes)
            if error:
                failed.append(error)
                continue

            content_hash = hashlib.sha256(pdf_bytes).hexdigest()
            existing = await store.find_by_hash(content_hash)
            if existing:
                logger.info(f"{file.filename}: Duplikat erkannt (bereits als '{existing['filename']}' indexiert)")
                uploaded.append(UploadedDocument(
                    id=existing["doc_id"],
                    type=doc_type,
                    filename=existing["filename"],
                    text_length=existing["text_length"],
                    ocr_used=False,
                    status="duplicate",
                    duplicate_of=existing["doc_id"],
                ))
                continue

            text, ocr_used = extract_text_from_pdf(pdf_bytes)
            if not text.strip():
                failed.append(f"{file.filename}: kein Text extrahierbar (auch nach OCR)")
                continue

            doc_id = str(uuid.uuid4())
            vector = await provider.embed(text)
            await store.upsert(
                doc_id=doc_id,
                doc_type=doc_type.value,
                filename=file.filename,
                text=text,
                vector=vector,
                content_hash=content_hash,
            )
            if ocr_used:
                logger.info(f"{file.filename}: OCR wurde für mindestens eine Seite verwendet")

            uploaded.append(
                UploadedDocument(
                    id=doc_id,
                    type=doc_type,
                    filename=file.filename,
                    text_length=len(text),
                    ocr_used=ocr_used,
                )
            )
        except Exception as e:
            logger.error(f"Fehler bei {file.filename}: {e}")
            failed.append(f"{file.filename}: {str(e)}")

    return BatchUploadResponse(documents=uploaded, total=len(uploaded), failed=failed)


@router.post(
    "/cvs/batch",
    response_model=BatchUploadResponse,
    summary="CVs als PDF hochladen (Batch)",
    description="""
Lädt einen oder mehrere Lebensläufe als PDF-Dateien hoch.

**Verarbeitungsschritte:**
1. Text-Extraktion via PyMuPDF
2. Bei Scan-PDFs (weniger als 50 Zeichen pro Seite): automatischer OCR-Fallback via Tesseract (Deutsch + Englisch)
3. Embedding-Erstellung via KI-Provider
4. Speicherung in Qdrant-Vektordatenbank

Das Feld `ocr_used` im Response zeigt an, ob OCR für dieses Dokument benötigt wurde.
""",
)
async def upload_cvs(
    files: list[UploadFile] = File(..., description="Ein oder mehrere CV-PDFs (multipart/form-data)"),
    provider: AIProvider = Depends(get_provider),
    store: VectorStore = Depends(get_vector_store),
):
    return await _ingest_pdfs(files, DocumentType.cv, provider, store)


@router.post(
    "/jobs/batch",
    response_model=BatchUploadResponse,
    summary="Stellenbeschreibungen als PDF hochladen (Batch)",
    description="""
Lädt eine oder mehrere Stellenbeschreibungen als PDF-Dateien hoch.

Identischer Verarbeitungsprozess wie beim CV-Upload — inkl. OCR-Fallback für Scan-PDFs.
""",
)
async def upload_jobs(
    files: list[UploadFile] = File(..., description="Ein oder mehrere Stellenbeschreibungs-PDFs (multipart/form-data)"),
    provider: AIProvider = Depends(get_provider),
    store: VectorStore = Depends(get_vector_store),
):
    return await _ingest_pdfs(files, DocumentType.job, provider, store)


@router.get(
    "/documents",
    response_model=DocumentListResponse,
    summary="Alle Dokumente auflisten (paginiert)",
    description="""
Gibt eine paginierte Übersicht aller im Index gespeicherten Dokumente zurück.

**Pagination:** Cursor-basiert — der `next_cursor` aus der Antwort wird im nächsten Request als `cursor`-Parameter übergeben.
Wenn `next_cursor` null ist, gibt es keine weitere Seite.

**Filterung:** Optional nach `type` (`cv` oder `job`) filtern.
""",
)
async def list_documents(
    type: DocumentType | None = Query(default=None, description="Filter: nur 'cv' oder nur 'job' zurückgeben"),
    limit: int = Query(default=20, ge=1, le=100, description="Einträge pro Seite"),
    cursor: str | None = Query(default=None, description="Cursor der vorherigen Seite (aus next_cursor)"),
    store: VectorStore = Depends(get_vector_store),
):
    try:
        doc_type = type.value if type else None
        total = await store.count_documents(doc_type)
        items_raw, next_cursor = await store.list_documents(doc_type=doc_type, limit=limit, cursor=cursor)
    except _CONNECTION_ERRORS:
        raise HTTPException(status_code=503, detail=_SERVICE_DOWN)

    items = [
        DocumentListItem(
            id=d["doc_id"],
            type=DocumentType(d["doc_type"]),
            filename=d["filename"],
            text_length=d["text_length"],
        )
        for d in items_raw
    ]
    return DocumentListResponse(items=items, total=total, limit=limit, next_cursor=next_cursor)


@router.get(
    "/documents/{document_id}",
    response_model=DocumentDetail,
    summary="Einzelnes Dokument abrufen",
    description="Gibt Metadaten und den vollständig extrahierten Text eines indizierten Dokuments zurück.",
)
async def get_document(
    document_id: str,
    store: VectorStore = Depends(get_vector_store),
):
    try:
        doc = await store.get_by_doc_id(document_id)
    except _CONNECTION_ERRORS:
        raise HTTPException(status_code=503, detail=_SERVICE_DOWN)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Dokument '{document_id}' nicht gefunden.")
    return DocumentDetail(
        id=doc["doc_id"],
        type=DocumentType(doc["doc_type"]),
        filename=doc["filename"],
        text=doc["text"],
        text_length=len(doc["text"]),
    )


@router.delete(
    "/documents/{document_id}",
    response_model=DeleteResponse,
    summary="Dokument löschen",
    description="Entfernt ein einzelnes Dokument dauerhaft aus dem Vektorindex.",
)
async def delete_document(
    document_id: str,
    store: VectorStore = Depends(get_vector_store),
):
    try:
        deleted = await store.delete(document_id)
    except _CONNECTION_ERRORS:
        raise HTTPException(status_code=503, detail=_SERVICE_DOWN)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Dokument '{document_id}' nicht gefunden.")
    return DeleteResponse(id=document_id, deleted=True)
