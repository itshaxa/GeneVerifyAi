"""Business logic layer.

Conventions:
- API routes must stay thin and delegate to services here.
- The deterministic STR matching engine lives in ``app/services/str_engine``
  and must NEVER depend on AI/LLM code.
- AI capabilities live behind the abstractions in ``app/services/ai`` so the
  provider (e.g. Alibaba Cloud Qwen) can be swapped or mocked without
  touching the core verification logic.
"""
