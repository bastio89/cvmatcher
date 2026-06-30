import logging
import uuid
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
from app.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "documents"


class VectorStore:
    def __init__(self, dimensions: int):
        self._client = AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
        self._dimensions = dimensions

    async def ensure_collection(self):
        collections = await self._client.get_collections()
        names = [c.name for c in collections.collections]
        if COLLECTION_NAME not in names:
            await self._client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=self._dimensions, distance=Distance.COSINE),
            )
            logger.info(f"Qdrant-Collection '{COLLECTION_NAME}' erstellt (dim={self._dimensions})")

    async def upsert(self, doc_id: str, doc_type: str, filename: str, text: str, vector: list[float]) -> str:
        point = PointStruct(
            id=str(uuid.uuid5(uuid.NAMESPACE_URL, doc_id)),
            vector=vector,
            payload={
                "doc_id": doc_id,
                "doc_type": doc_type,
                "filename": filename,
                "text": text,
            },
        )
        await self._client.upsert(collection_name=COLLECTION_NAME, points=[point])
        return doc_id

    async def search(self, query_vector: list[float], doc_type: str, top_k: int = 10) -> list[dict]:
        results = await self._client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            query_filter=Filter(
                must=[FieldCondition(key="doc_type", match=MatchValue(value=doc_type))]
            ),
            limit=top_k,
            with_payload=True,
        )
        return [
            {
                "doc_id": r.payload["doc_id"],
                "doc_type": r.payload["doc_type"],
                "filename": r.payload["filename"],
                "text": r.payload["text"],
                "score": r.score,
            }
            for r in results
        ]

    async def get_by_doc_id(self, doc_id: str) -> dict | None:
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, doc_id))
        results = await self._client.retrieve(
            collection_name=COLLECTION_NAME,
            ids=[point_id],
            with_payload=True,
            with_vectors=True,
        )
        if not results:
            return None
        p = results[0]
        return {
            "doc_id": p.payload["doc_id"],
            "doc_type": p.payload["doc_type"],
            "filename": p.payload["filename"],
            "text": p.payload["text"],
            "vector": p.vector,
        }

    async def delete(self, doc_id: str) -> bool:
        """Löscht ein Dokument aus dem Index. Gibt False zurück wenn es nicht existiert."""
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, doc_id))
        existing = await self._client.retrieve(
            collection_name=COLLECTION_NAME, ids=[point_id], with_payload=False, with_vectors=False
        )
        if not existing:
            return False
        await self._client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=[point_id],
        )
        return True

    async def list_documents(
        self,
        doc_type: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> tuple[list[dict], str | None]:
        """
        Cursor-basierte Paginierung über alle Dokumente.
        Gibt (items, next_cursor) zurück — next_cursor ist None wenn keine weitere Seite existiert.
        """
        scroll_filter = None
        if doc_type:
            scroll_filter = Filter(
                must=[FieldCondition(key="doc_type", match=MatchValue(value=doc_type))]
            )

        points, next_offset = await self._client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=scroll_filter,
            limit=limit,
            offset=cursor,
            with_payload=True,
            with_vectors=False,
        )

        items = [
            {
                "doc_id": p.payload["doc_id"],
                "doc_type": p.payload["doc_type"],
                "filename": p.payload["filename"],
                "text_length": len(p.payload.get("text", "")),
            }
            for p in points
        ]
        next_cursor = str(next_offset) if next_offset is not None else None
        return items, next_cursor

    async def count_documents(self, doc_type: str | None = None) -> int:
        """Gibt die Gesamtanzahl der Dokumente zurück, optional gefiltert nach Typ."""
        count_filter = None
        if doc_type:
            count_filter = Filter(
                must=[FieldCondition(key="doc_type", match=MatchValue(value=doc_type))]
            )
        result = await self._client.count(
            collection_name=COLLECTION_NAME,
            count_filter=count_filter,
            exact=True,
        )
        return result.count
