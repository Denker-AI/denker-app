from .base import EmbeddingProvider
from .types import EmbeddingProviderType
from ..settings import EmbeddingProviderSettings


def create_embedding_provider(settings: EmbeddingProviderSettings) -> EmbeddingProvider:
    """
    Create an embedding provider based on the specified type.
    :param settings: The settings for the embedding provider.
    :return: An instance of the specified embedding provider.
    """
    if settings.provider_type == EmbeddingProviderType.FASTEMBED:
        from .fastembed import FastEmbedProvider

        return FastEmbedProvider(settings.model_name)
    else:
        raise ValueError(f"Unsupported embedding provider: {settings.provider_type}")
