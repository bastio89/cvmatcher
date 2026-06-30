import logging
import uuid
from app.models.schemas import (
    BatchMatchEntry,
    BatchMatchResponse,
    DocumentType,
    MatchAnalysis,
    MatchResponse,
    MatchResult,
    ScoringWeights,
    SkillMatch,
)
from app.providers.base import AIProvider
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)


def _compute_final_score(similarity_score: float, llm_score: int | None, weights: ScoringWeights) -> float:
    """
    Berechnet den gewichteten Gesamtscore.
    - similarity_score: Kosinus-Ähnlichkeit (0.0–1.0)
    - llm_score: LLM-Bewertung (0–100), None wenn keine Analyse
    - Wenn kein LLM-Score vorhanden: 100 % Vektor-Gewicht
    """
    if llm_score is None:
        return round(similarity_score, 4)
    llm_normalized = llm_score / 100.0
    score = weights.vector * similarity_score + weights.llm * llm_normalized
    return round(score, 4)


class MatcherService:
    def __init__(self, provider: AIProvider, vector_store: VectorStore):
        self._provider = provider
        self._store = vector_store

    async def match(
        self,
        document_id: str,
        document_type: DocumentType,
        top_k: int = 10,
        include_analysis: bool = True,
        scoring: ScoringWeights | None = None,
    ) -> MatchResponse:
        if scoring is None:
            scoring = ScoringWeights()

        source = await self._store.get_by_doc_id(document_id)
        if source is None:
            raise ValueError(f"Dokument '{document_id}' nicht in der Datenbank gefunden.")

        target_type = DocumentType.job if document_type == DocumentType.cv else DocumentType.cv
        candidates = await self._store.search(
            query_vector=source["vector"],
            doc_type=target_type.value,
            top_k=top_k,
        )

        results = []
        for candidate in candidates:
            analysis = None
            if include_analysis:
                try:
                    raw = await self._provider.analyze_match(
                        source_text=source["text"],
                        target_text=candidate["text"],
                        source_type=document_type.value,
                        target_type=target_type.value,
                    )
                    analysis = MatchAnalysis(
                        overall_score=raw.get("overall_score", 50),
                        overall_label=raw.get("overall_label", "Moderate"),
                        summary=raw.get("summary", ""),
                        skills=SkillMatch(**raw.get("skills", {})),
                        strengths=raw.get("strengths", []),
                        gaps=raw.get("gaps", []),
                    )
                except Exception as e:
                    logger.warning(f"Analyse für {candidate['doc_id']} fehlgeschlagen: {e}")

            llm_score = analysis.overall_score if analysis else None
            final_score = _compute_final_score(candidate["score"], llm_score, scoring)

            results.append(
                MatchResult(
                    rank=0,  # wird nach dem Sortieren gesetzt
                    document_id=candidate["doc_id"],
                    document_type=target_type,
                    filename=candidate["filename"],
                    similarity_score=round(candidate["score"], 4),
                    final_score=final_score,
                    analysis=analysis,
                )
            )

        results.sort(key=lambda r: r.final_score, reverse=True)
        for i, r in enumerate(results):
            r.rank = i + 1

        return MatchResponse(
            match_id=str(uuid.uuid4()),
            query_document_id=document_id,
            query_document_type=document_type,
            target_type=target_type,
            scoring=scoring,
            results=results,
            total_candidates=len(candidates),
        )

    async def batch_match(
        self,
        document_ids: list[str],
        document_type: DocumentType,
        top_k: int = 5,
        include_analysis: bool = True,
        scoring: ScoringWeights | None = None,
    ) -> BatchMatchResponse:
        if scoring is None:
            scoring = ScoringWeights()

        entries: list[BatchMatchEntry] = []

        for doc_id in document_ids:
            try:
                source = await self._store.get_by_doc_id(doc_id)
                if source is None:
                    entries.append(BatchMatchEntry(
                        document_id=doc_id,
                        filename="",
                        status="error",
                        error=f"Dokument '{doc_id}' nicht gefunden",
                    ))
                    continue

                match_result = await self.match(
                    document_id=doc_id,
                    document_type=document_type,
                    top_k=top_k,
                    include_analysis=include_analysis,
                    scoring=scoring,
                )
                entries.append(BatchMatchEntry(
                    document_id=doc_id,
                    filename=source["filename"],
                    status="ok",
                    match=match_result,
                ))
            except Exception as e:
                logger.error(f"Batch-Match fehlgeschlagen für {doc_id}: {e}")
                entries.append(BatchMatchEntry(
                    document_id=doc_id,
                    filename="",
                    status="error",
                    error=str(e),
                ))

        successful = sum(1 for e in entries if e.status == "ok")
        return BatchMatchResponse(
            document_type=document_type,
            total_sources=len(document_ids),
            successful=successful,
            failed=len(document_ids) - successful,
            results=entries,
        )
