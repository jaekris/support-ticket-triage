import pytest

from src.config import load_config


def test_load_config_succeeds_without_api_key(monkeypatch):
    """The app must import and configure with no key present — a client
    supplies their own key at runtime via ANTHROPIC_API_KEY."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config = load_config()
    assert config.anthropic_api_key == ""
    assert config.has_api_key is False


def test_load_config_reads_key_when_present(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
    config = load_config()
    assert config.anthropic_api_key == "sk-test-123"
    assert config.has_api_key is True


def test_require_api_key_raises_clear_error_when_missing(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config = load_config()
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        config.require_api_key()


def test_require_api_key_returns_key_when_present(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
    config = load_config()
    assert config.require_api_key() == "sk-test-123"


def test_max_concurrency_defaults_and_is_int(monkeypatch):
    monkeypatch.delenv("MAX_CONCURRENCY", raising=False)
    config = load_config()
    assert isinstance(config.max_concurrency, int)
    assert config.max_concurrency >= 1
