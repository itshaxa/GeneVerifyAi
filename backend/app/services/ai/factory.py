"""Provider factory for the document-intelligence abstraction.

Routes depend on the :class:`DocumentIntelligenceService` interface only;
this factory decides which concrete provider to instantiate based on the
``AI_PROVIDER`` environment setting. Production may never silently fall
back to the deterministic mock provider.
"""

from app.core.config import Settings
from app.services.ai.base import DocumentIntelligenceService


class AiProviderNotConfiguredError(RuntimeError):
    """Raised when the requested AI provider cannot be used."""


def create_document_intelligence_service(settings: Settings) -> DocumentIntelligenceService:
    """Build the configured document-intelligence provider."""
    provider = settings.ai_provider

    if provider == "mock":
        if settings.app_env == "production":
            raise AiProviderNotConfiguredError(
                "AI provider is not configured (mock provider is disabled in production)."
            )
        from app.services.ai.mock import MockDocumentIntelligenceService

        return MockDocumentIntelligenceService()

    if provider == "qwen":
        from app.services.ai.qwen import QwenDocumentIntelligenceService

        if not settings.qwen_api_key:
            raise AiProviderNotConfiguredError("AI provider is not configured.")
        return QwenDocumentIntelligenceService(
            api_key=settings.qwen_api_key,
            model=settings.qwen_model,
            base_url=settings.qwen_base_url,
            timeout_seconds=settings.qwen_timeout_seconds,
        )

    raise AiProviderNotConfiguredError("AI provider is not configured.")
