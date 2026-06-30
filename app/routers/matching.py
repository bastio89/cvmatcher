from fastapi import APIRouter, Depends, HTTPException
from app.models.schemas import BatchMatchRequest, BatchMatchResponse, MatchRequest, MatchResponse
from app.services.matcher import MatcherService
from app.dependencies import get_matcher

router = APIRouter()


@router.post(
    "/match",
    response_model=MatchResponse,
    summary="Einzelnes Dokument matchen",
    description="""
Matcht ein einzelnes Dokument gegen alle Dokumente des jeweils anderen Typs.

- **CV als Quelle** → findet passende Stellenbeschreibungen
- **Job als Quelle** → findet passende CVs (Kandidaten-Ranking)

Das Ranking basiert auf einem gewichteten `final_score` aus Vektor-Ähnlichkeit und LLM-Score.
Die Gewichtung ist über das `scoring`-Feld konfigurierbar (Standard: 30 % Vektor, 70 % LLM).
""",
)
async def run_match(
    request: MatchRequest,
    matcher: MatcherService = Depends(get_matcher),
):
    try:
        return await matcher.match(
            document_id=request.document_id,
            document_type=request.document_type,
            top_k=request.top_k,
            include_analysis=request.include_analysis,
            scoring=request.scoring,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Matching-Fehler: {str(e)}")


@router.post(
    "/match/batch",
    response_model=BatchMatchResponse,
    summary="Mehrere Dokumente gleichzeitig matchen (Batch)",
    description="""
Matcht mehrere Quell-Dokumente auf einmal gegen alle Dokumente des jeweils anderen Typs.

**Typische Anwendungsfälle:**
- N CVs gegen alle gespeicherten Jobs matchen → welche Stelle passt für jeden Kandidaten am besten?
- N Stellenbeschreibungen gegen alle gespeicherten CVs matchen → wer passt auf welche Stelle?

Jedes Quell-Dokument erhält ein eigenes Ranking-Ergebnis. Fehlgeschlagene Einzeldokumente
werden als `status: "error"` markiert, der Rest wird trotzdem verarbeitet.

Die `scoring`-Gewichtung gilt einheitlich für alle Dokumente im Batch.

**Limit:** maximal 500 Quell-Dokumente pro Request.
""",
)
async def run_batch_match(
    request: BatchMatchRequest,
    matcher: MatcherService = Depends(get_matcher),
):
    try:
        return await matcher.batch_match(
            document_ids=request.document_ids,
            document_type=request.document_type,
            top_k=request.top_k,
            include_analysis=request.include_analysis,
            scoring=request.scoring,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch-Matching-Fehler: {str(e)}")
