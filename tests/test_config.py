import pytest

from library_management_system.config import get_settings


def test_local_environment_is_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)

    settings = get_settings()

    assert settings.environment == "local"
    assert settings.auto_create_schema is True
    assert settings.synopsis_embedding_dimensions == 1536


def test_production_disables_automatic_schema_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")

    settings = get_settings()

    assert settings.environment == "production"
    assert settings.auto_create_schema is False


def test_environment_overrides_are_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("AGENT_MODEL", "openai:test-model")
    monkeypatch.setenv("SYNOPSIS_EMBEDDING_DIMENSIONS", "8")

    settings = get_settings()

    assert settings.agent_model == "openai:test-model"
    assert settings.synopsis_embedding_dimensions == 8


def test_unknown_environment_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "staging")

    with pytest.raises(ValueError, match="APP_ENV"):
        get_settings()
