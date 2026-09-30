"""Live LLM tests — require real API keys; excluded from default `make test`.

Set LLM_PROVIDER + the matching key, then run `make test-all`.
"""
import pytest

from src.agents.nodes import llm_route
from src.services.llm_factory import provider_status

_, _, key_present, _ = provider_status()
needs_key = pytest.mark.skipif(not key_present, reason="no LLM key configured")


@needs_key
def test_llm_router_order():
    d = llm_route("Where is invoice 1004? My email is elena.vargas@example.com")
    assert d.intent == "order_lookup"
    assert 0.0 <= d.confidence <= 1.0
