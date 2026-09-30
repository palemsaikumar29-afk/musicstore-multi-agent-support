"""LLM factory unit tests (no network): offline paths only."""
import pytest

from src.services import config
from src.services.llm_factory import LLMOffline, provider_status


def test_provider_status_offline(monkeypatch):
    monkeypatch.setattr(config.settings, "llm_provider", "groq")
    monkeypatch.setattr(config.settings, "groq_api_key", "")
    provider, _model, present, reason = provider_status()
    assert provider == "groq" and present is False and reason


def test_provider_status_live(monkeypatch):
    monkeypatch.setattr(config.settings, "llm_provider", "gemini")
    monkeypatch.setattr(config.settings, "gemini_api_key", "dummy-key")
    provider, _model, present, reason = provider_status()
    assert provider == "gemini" and present is True and reason == ""


def test_get_llm_offline_raises(monkeypatch):
    from src.services.llm_factory import get_llm

    monkeypatch.setattr(config.settings, "llm_provider", "openai")
    monkeypatch.setattr(config.settings, "openai_api_key", "")
    with pytest.raises(LLMOffline):
        get_llm()


def test_get_llm_bad_provider(monkeypatch):
    from src.services.llm_factory import get_llm

    monkeypatch.setattr(config.settings, "llm_provider", "nope")
    with pytest.raises(ValueError):
        get_llm()
