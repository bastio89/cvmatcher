from abc import ABC, abstractmethod


class AIProvider(ABC):
    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Erstellt einen Embedding-Vektor für den gegebenen Text."""
        ...

    @abstractmethod
    async def analyze_match(self, source_text: str, target_text: str, source_type: str, target_type: str) -> dict:
        """Analysiert die Passung zwischen zwei Dokumenten und gibt strukturiertes Feedback zurück."""
        ...

    @property
    @abstractmethod
    def embedding_dimensions(self) -> int:
        """Dimension der Embedding-Vektoren (modellabhängig)."""
        ...
