"""
Anthropic/Claude Provider — für zukünftige Cloud-Erweiterung.

Aktivieren via: AI_PROVIDER=anthropic in .env
Benötigt: pip install anthropic voyageai
"""
import json
import logging
from app.providers.base import AIProvider
from app.config import settings

logger = logging.getLogger(__name__)


class AnthropicProvider(AIProvider):
    """
    Nutzt Claude für LLM-Analyse und Voyage AI für Embeddings.
    Voyage AI ist Anthropics empfohlener Embedding-Partner.
    """

    def __init__(self):
        try:
            import anthropic
            import voyageai
        except ImportError:
            raise RuntimeError(
                "Anthropic provider benötigt: pip install anthropic voyageai\n"
                "Setze außerdem ANTHROPIC_API_KEY in .env"
            )

        self._anthropic = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._voyage = voyageai.AsyncClient()
        self._llm_model = settings.anthropic_llm_model
        self._embed_model = settings.anthropic_embedding_model

    @property
    def embedding_dimensions(self) -> int:
        # voyage-3: 1024 dims
        return 1024

    async def embed(self, text: str) -> list[float]:
        result = await self._voyage.embed([text], model=self._embed_model)
        return result.embeddings[0]

    async def analyze_match(self, source_text: str, target_text: str, source_type: str, target_type: str) -> dict:
        from app.providers.ollama_provider import ANALYSIS_PROMPT

        labels = {
            "cv": ("CV / Lebenslauf", "Stellenbeschreibung"),
            "job": ("Stellenbeschreibung", "CV / Lebenslauf"),
        }
        source_label, target_label = labels.get(source_type, (source_type, target_type))

        prompt = ANALYSIS_PROMPT.format(
            source_type=source_label,
            target_type=target_label,
            source_label=source_label,
            source_text=source_text[:4000],
            target_label=target_label,
            target_text=target_text[:4000],
        )

        message = await self._anthropic.messages.create(
            model=self._llm_model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Claude returned non-JSON, using fallback")
            return {
                "overall_score": 50,
                "overall_label": "Moderate",
                "summary": raw[:500],
                "skills": {"matching": [], "missing": [], "bonus": []},
                "strengths": [],
                "gaps": [],
            }
