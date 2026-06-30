from functools import lru_cache
from app.config import settings
from app.providers.base import AIProvider
from app.services.vector_store import VectorStore
from app.services.matcher import MatcherService


@lru_cache(maxsize=1)
def get_provider() -> AIProvider:
    if settings.ai_provider == "anthropic":
        from app.providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider()
    from app.providers.ollama_provider import OllamaProvider
    return OllamaProvider()


@lru_cache(maxsize=1)
def get_vector_store() -> VectorStore:
    provider = get_provider()
    return VectorStore(dimensions=provider.embedding_dimensions)


def get_matcher() -> MatcherService:
    return MatcherService(provider=get_provider(), vector_store=get_vector_store())
