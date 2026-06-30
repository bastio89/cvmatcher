from enum import Enum
from pydantic import BaseModel, Field, model_validator
import uuid


class DocumentType(str, Enum):
    cv = "cv"
    job = "job"


class ScoringWeights(BaseModel):
    vector: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Gewicht der Vektor-Ähnlichkeit (0.0–1.0). Zusammen mit llm muss die Summe 1.0 ergeben.",
        examples=[0.3],
    )
    llm: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Gewicht des LLM-Scores (0.0–1.0). Wird ignoriert wenn include_analysis=false.",
        examples=[0.7],
    )

    @model_validator(mode="after")
    def weights_must_sum_to_one(self) -> "ScoringWeights":
        if abs(self.vector + self.llm - 1.0) > 0.01:
            raise ValueError(f"vector + llm muss 1.0 ergeben, aktuell: {self.vector + self.llm:.2f}")
        return self

    model_config = {
        "json_schema_extra": {
            "example": {"vector": 0.3, "llm": 0.7}
        }
    }


class UploadedDocument(BaseModel):
    id: str = Field(examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"])
    type: DocumentType
    filename: str = Field(examples=["lebenslauf_max_mustermann.pdf"])
    text_length: int = Field(description="Anzahl extrahierter Zeichen", examples=[3240])
    ocr_used: bool = Field(description="True wenn Tesseract-OCR für Scan-Seiten eingesetzt wurde")
    status: str = Field(default="indexed", description="'indexed', 'duplicate'", examples=["indexed"])
    duplicate_of: str | None = Field(
        default=None,
        description="ID des bereits indexierten Dokuments — gesetzt wenn status='duplicate'",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "type": "cv",
                "filename": "lebenslauf_max_mustermann.pdf",
                "text_length": 3240,
                "ocr_used": False,
                "status": "indexed",
            }
        }
    }


class BatchUploadResponse(BaseModel):
    documents: list[UploadedDocument]
    total: int = Field(description="Anzahl erfolgreich indexierter Dokumente", examples=[2])
    failed: list[str] = Field(
        default=[],
        description="Dateinamen und Fehlermeldungen für fehlgeschlagene Uploads",
        examples=[[]],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "documents": [
                    {
                        "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                        "type": "cv",
                        "filename": "lebenslauf_max_mustermann.pdf",
                        "text_length": 3240,
                        "ocr_used": False,
                        "status": "indexed",
                    }
                ],
                "total": 1,
                "failed": [],
            }
        }
    }


class DocumentListItem(BaseModel):
    id: str = Field(examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"])
    type: DocumentType
    filename: str = Field(examples=["lebenslauf_max_mustermann.pdf"])
    text_length: int = Field(description="Anzahl gespeicherter Zeichen", examples=[3240])


class DocumentListResponse(BaseModel):
    items: list[DocumentListItem]
    total: int = Field(description="Gesamtanzahl Dokumente (gefiltert)")
    limit: int = Field(description="Einträge pro Seite")
    next_cursor: str | None = Field(
        default=None,
        description="Cursor für die nächste Seite — null wenn keine weitere Seite existiert",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "items": [
                    {"id": "a1b2c3d4-...", "type": "cv", "filename": "cv_max_mustermann.pdf", "text_length": 3240},
                    {"id": "b2c3d4e5-...", "type": "cv", "filename": "cv_anna_schmidt.pdf",   "text_length": 2890},
                ],
                "total": 42,
                "limit": 20,
                "next_cursor": "c3d4e5f6-a7b8-9012-cdef-012345678902",
            }
        }
    }


class MatchRequest(BaseModel):
    document_id: str = Field(
        description="ID des Quell-Dokuments (aus dem Upload-Response)",
        examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"],
    )
    document_type: DocumentType = Field(
        description="Typ des Quell-Dokuments: 'cv' sucht passende Jobs, 'job' sucht passende CVs"
    )
    top_k: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximale Anzahl zurückgegebener Treffer",
        examples=[10],
    )
    include_analysis: bool = Field(
        default=True,
        description="LLM-Detailanalyse pro Treffer (langsamer, aber mit Begründung und Skill-Aufschlüsselung)",
        examples=[True],
    )
    scoring: ScoringWeights = Field(
        default_factory=ScoringWeights,
        description="Gewichtung von Vektor-Score vs. LLM-Score für das Ranking. Wird ignoriert wenn include_analysis=false.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "document_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "document_type": "job",
                "top_k": 5,
                "include_analysis": True,
                "scoring": {"vector": 0.3, "llm": 0.7},
            }
        }
    }


class SkillMatch(BaseModel):
    matching: list[str] = Field(default=[], description="Skills die CV und Stelle gemeinsam haben", examples=[["Python", "FastAPI", "PostgreSQL"]])
    missing: list[str] = Field(default=[], description="Geforderte Skills die im CV fehlen", examples=[["Kubernetes"]])
    bonus: list[str] = Field(default=[], description="Zusatzqualifikationen im CV die nicht gefordert wurden", examples=[["Rust", "Open-Source-Erfahrung"]])


class MatchAnalysis(BaseModel):
    overall_score: int = Field(description="Gesamtbewertung 0–100", ge=0, le=100, examples=[87])
    overall_label: str = Field(description="Bewertungsstufe: Excellent / Good / Moderate / Poor", examples=["Excellent"])
    summary: str = Field(description="2–3 Sätze Gesamteinschätzung der Passung", examples=["Max Mustermann bringt 5 Jahre Python-Erfahrung mit und deckt den Großteil der geforderten Skills ab. Lediglich Kubernetes-Kenntnisse fehlen, könnten aber kurzfristig erlernt werden."])
    skills: SkillMatch
    strengths: list[str] = Field(default=[], examples=[["Starke Backend-Erfahrung", "Nachgewiesene API-Projekte"]])
    gaps: list[str] = Field(default=[], examples=[["Keine Erfahrung mit Container-Orchestrierung"]])


class MatchResult(BaseModel):
    rank: int = Field(description="Position im Ranking (1 = beste Übereinstimmung)", examples=[1])
    document_id: str = Field(examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"])
    document_type: DocumentType
    filename: str = Field(examples=["lebenslauf_max_mustermann.pdf"])
    similarity_score: float = Field(
        description="Semantische Kosinus-Ähnlichkeit (0.0–1.0)",
        examples=[0.9124],
    )
    final_score: float = Field(
        description="Gewichteter Gesamtscore aus Vektor + LLM (0.0–1.0). Basis des Rankings.",
        examples=[0.8587],
    )
    analysis: MatchAnalysis | None = Field(
        default=None,
        description="LLM-Detailanalyse — nur vorhanden wenn include_analysis=true",
    )


class DocumentDetail(BaseModel):
    id: str = Field(examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"])
    type: DocumentType
    filename: str = Field(examples=["lebenslauf_max_mustermann.pdf"])
    text: str = Field(description="Vollständig extrahierter Text des Dokuments")
    text_length: int = Field(description="Anzahl Zeichen", examples=[3240])

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "type": "cv",
                "filename": "lebenslauf_max_mustermann.pdf",
                "text": "Max Mustermann\nSoftware Engineer...",
                "text_length": 3240,
            }
        }
    }


class DeleteResponse(BaseModel):
    id: str
    deleted: bool = Field(description="True wenn erfolgreich gelöscht")


class BatchMatchRequest(BaseModel):
    document_ids: list[str] = Field(
        description="Liste der Quell-Dokument-IDs (alle vom gleichen Typ)",
        min_length=1,
        max_length=500,
        examples=[["a1b2c3d4-e5f6-7890-abcd-ef1234567890", "b2c3d4e5-f6a7-8901-bcde-f01234567891"]],
    )
    document_type: DocumentType = Field(
        description="Typ aller Quell-Dokumente: 'cv' sucht Jobs, 'job' sucht CVs"
    )
    top_k: int = Field(default=5, ge=1, le=100, description="Top-Treffer pro Quell-Dokument", examples=[5])
    include_analysis: bool = Field(default=True, description="LLM-Analyse pro Treffer")
    scoring: ScoringWeights = Field(
        default_factory=ScoringWeights,
        description="Gewichtung von Vektor-Score vs. LLM-Score — gilt für alle Dokumente im Batch.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "document_ids": [
                    "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "b2c3d4e5-f6a7-8901-bcde-f01234567891",
                ],
                "document_type": "job",
                "top_k": 5,
                "include_analysis": True,
                "scoring": {"vector": 0.3, "llm": 0.7},
            }
        }
    }


class BatchMatchEntry(BaseModel):
    document_id: str
    filename: str
    status: str = Field(description="'ok' oder 'error'")
    error: str | None = Field(default=None, description="Fehlermeldung bei status='error'")
    match: MatchResponse | None = None


class BatchMatchResponse(BaseModel):
    batch_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Eindeutige ID dieses Batch-Vorgangs",
    )
    document_type: DocumentType
    total_sources: int = Field(description="Anzahl der Quell-Dokumente")
    successful: int = Field(description="Erfolgreich gematchte Dokumente")
    failed: int = Field(description="Fehlgeschlagene Dokumente")
    results: list[BatchMatchEntry]


class MatchResponse(BaseModel):
    match_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Eindeutige ID dieses Match-Vorgangs",
        examples=["f9e8d7c6-b5a4-3210-fedc-ba9876543210"],
    )
    query_document_id: str = Field(examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"])
    query_document_type: DocumentType
    target_type: DocumentType
    scoring: ScoringWeights = Field(description="Verwendete Score-Gewichtung")
    results: list[MatchResult]
    total_candidates: int = Field(description="Gesamtanzahl gefundener Kandidaten", examples=[5])

    model_config = {
        "json_schema_extra": {
            "example": {
                "match_id": "f9e8d7c6-b5a4-3210-fedc-ba9876543210",
                "query_document_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "query_document_type": "job",
                "target_type": "cv",
                "scoring": {"vector": 0.3, "llm": 0.7},
                "total_candidates": 1,
                "results": [
                    {
                        "rank": 1,
                        "document_id": "b2c3d4e5-f6a7-8901-bcde-f01234567891",
                        "document_type": "cv",
                        "filename": "lebenslauf_max_mustermann.pdf",
                        "similarity_score": 0.9124,
                        "final_score": 0.8787,
                        "analysis": {
                            "overall_score": 87,
                            "overall_label": "Excellent",
                            "summary": "Max Mustermann bringt 5 Jahre Python-Erfahrung mit und deckt den Großteil der geforderten Skills ab.",
                            "skills": {
                                "matching": ["Python", "FastAPI", "PostgreSQL"],
                                "missing": ["Kubernetes"],
                                "bonus": ["Rust", "Open-Source-Erfahrung"],
                            },
                            "strengths": ["Starke Backend-Erfahrung", "Nachgewiesene API-Projekte"],
                            "gaps": ["Keine Erfahrung mit Container-Orchestrierung"],
                        },
                    }
                ],
            }
        }
    }
