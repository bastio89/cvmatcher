import json
import logging
import httpx
from app.providers.base import AIProvider
from app.config import settings

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT = """Du bist ein erfahrener HR-Analyst. Analysiere die Passung zwischen folgendem {source_type} und {target_type}.

{source_label}:
{source_text}

---

{target_label}:
{target_text}

---

Antworte NUR mit einem validen JSON-Objekt (kein Markdown, keine Erklärung außerhalb des JSON):
{{
  "overall_score": <Zahl 0-100>,
  "overall_label": "<Excellent|Good|Moderate|Poor>",
  "summary": "<2-3 Sätze Gesamteinschätzung>",
  "skills": {{
    "matching": ["<Skill>", ...],
    "missing": ["<geforderter Skill fehlt im CV>", ...],
    "bonus": ["<Zusatzqualifikation im CV>", ...]
  }},
  "strengths": ["<Stärke 1>", "<Stärke 2>"],
  "gaps": ["<Lücke 1>", "<Lücke 2>"]
}}"""


class OllamaProvider(AIProvider):
    def __init__(self):
        self._host = settings.ollama_host
        self._embed_model = settings.embedding_model
        self._llm_model = settings.llm_model
        self._dimensions = None

    @property
    def embedding_dimensions(self) -> int:
        # nomic-embed-text: 768 dims
        return 768

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=settings.ollama_embed_timeout) as client:
            response = await client.post(
                f"{self._host}/api/embeddings",
                json={"model": self._embed_model, "prompt": text},
            )
            response.raise_for_status()
            return response.json()["embedding"]

    async def analyze_match(self, source_text: str, target_text: str, source_type: str, target_type: str) -> dict:
        labels = {
            "cv": ("CV / Lebenslauf", "Stellenbeschreibung"),
            "job": ("Stellenbeschreibung", "CV / Lebenslauf"),
        }
        source_label, target_label = labels.get(source_type, (source_type, target_type))

        prompt = ANALYSIS_PROMPT.format(
            source_type=source_label,
            target_type=target_label,
            source_label=source_label,
            source_text=source_text[:3000],
            target_label=target_label,
            target_text=target_text[:3000],
        )

        async with httpx.AsyncClient(timeout=settings.ollama_timeout) as client:
            response = await client.post(
                f"{self._host}/api/generate",
                json={"model": self._llm_model, "prompt": prompt, "stream": False},
            )
            response.raise_for_status()
            raw = response.json()["response"].strip()

        # Extrahiere JSON falls das Modell Markdown-Blöcke ausgibt
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM hat kein valides JSON zurückgegeben: {raw[:200]}") from exc
