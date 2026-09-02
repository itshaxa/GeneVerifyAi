"""AI provider abstraction layer.

Concrete providers (Alibaba Cloud Qwen, deterministic mock) live in this
package only. Routes and services depend on the abstract interfaces in
``base`` and receive an implementation through the factory/dependency
injection, so the deterministic verification core never imports AI code
directly.
"""

from app.services.ai.base import (
    AIProviderError,
    DocumentIntelligenceService,
    VerificationExplainerService,
)
from app.services.ai.factory import (
    AiProviderNotConfiguredError,
    create_document_intelligence_service,
)

__all__ = [
    "AIProviderError",
    "AiProviderNotConfiguredError",
    "DocumentIntelligenceService",
    "VerificationExplainerService",
    "create_document_intelligence_service",
]
