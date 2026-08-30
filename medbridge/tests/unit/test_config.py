import os
import pytest
from pydantic import ValidationError
from medbridge.config import Settings, get_settings

def test_defaults_applied(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test_key")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_pass")
    
    # We clear the environment of an existing .env configuration just in case
    # Pydantic might pick up `.env` from the project root.
    # To truly isolate, we mock out env file loading by patching the model config
    Settings.model_config["env_file"] = None
    
    settings = Settings()
    
    assert settings.GROQ_API_KEY == "test_key"
    assert settings.POSTGRES_PASSWORD == "test_pass"
    assert settings.LLM_MODEL == "llama-3.1-8b-instant"
    assert settings.LLM_TEMPERATURE_GATES == 0.0
    assert settings.LLM_SEED == 42
    assert settings.DATABASE_URL == "postgresql+asyncpg://medbridge_app:password@127.0.0.1:5432/medbridge"
    assert settings.QDRANT_URL == "http://127.0.0.1:6333"
    assert settings.CORS_ORIGINS == ["http://localhost:8501"]

def test_missing_required_raises(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    Settings.model_config["env_file"] = None
    
    with pytest.raises(ValidationError) as exc_info:
        Settings()
        
    errors = str(exc_info.value)
    assert "GROQ_API_KEY" in errors or "groq_api_key" in errors
    assert "POSTGRES_PASSWORD" in errors or "postgres_password" in errors

def test_type_coercion(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test_key")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_pass")
    monkeypatch.setenv("LLM_TEMPERATURE_GATES", "0.5")
    monkeypatch.setenv("LLM_MAX_TOKENS_GATES", "1024")
    monkeypatch.setenv("CORS_ORIGINS", '["http://test.com"]')
    Settings.model_config["env_file"] = None
    
    settings = Settings()
    
    assert settings.LLM_TEMPERATURE_GATES == 0.5
    assert settings.LLM_MAX_TOKENS_GATES == 1024
    assert settings.CORS_ORIGINS == ["http://test.com"]

def test_singleton_behavior(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test_key")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_pass")
    Settings.model_config["env_file"] = None
    
    get_settings.cache_clear()
    settings_1 = get_settings()
    settings_2 = get_settings()
    
    assert settings_1 is settings_2
