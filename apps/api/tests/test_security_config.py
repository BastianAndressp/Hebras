"""Antes, JWT_SECRET vacío desactivaba la verificación de firma en silencio (auth.py) y
la app arrancaba igual. Ahora Settings() debe fallar (fail-fast) si falta cualquiera de
estos tres valores obligatorios."""
import pytest
from pydantic import ValidationError

from app.config import Settings

BASE_ENV = {
    "JWT_SECRET": "a" * 32,
    "APP_ENCRYPTION_KEY": "b" * 32,
    "TENANT_DATABASE_URL": "postgresql://app_user:x@localhost:5432/whatsapp_ai",
}


def _set_env(monkeypatch, overrides: dict[str, str | None]):
    for key, value in {**BASE_ENV, **overrides}.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)


def test_settings_requires_jwt_secret(monkeypatch):
    _set_env(monkeypatch, {"JWT_SECRET": None})
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_requires_app_encryption_key(monkeypatch):
    _set_env(monkeypatch, {"APP_ENCRYPTION_KEY": None})
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_requires_tenant_database_url(monkeypatch):
    _set_env(monkeypatch, {"TENANT_DATABASE_URL": None})
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_loads_with_all_required_values(monkeypatch):
    _set_env(monkeypatch, {})
    settings = Settings(_env_file=None)
    assert settings.jwt_secret == BASE_ENV["JWT_SECRET"]
    assert settings.app_encryption_key == BASE_ENV["APP_ENCRYPTION_KEY"]
    assert settings.demo_mode is False
