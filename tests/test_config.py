"""Config validation and admin-key checks — no DB needed."""
import pytest
from fastapi import HTTPException

import config


def _set(monkeypatch, **kw):
    for k, v in kw.items():
        monkeypatch.setattr(config, k, v)


def test_local_requires_only_database_url(monkeypatch):
    _set(monkeypatch, APP_ENV="local", DATABASE_URL="postgresql://u:x@h/db", ADMIN_KEY="")
    assert config.validate() == []
    _set(monkeypatch, DATABASE_URL=None)
    assert any("DATABASE_URL" in e for e in config.validate())


def test_unknown_env_rejected(monkeypatch):
    _set(monkeypatch, APP_ENV="prod", DATABASE_URL="postgresql://u:x@h/db")
    assert any("APP_ENV" in e for e in config.validate())


@pytest.mark.parametrize("env", ["staging", "production"])
def test_deployed_rejects_missing_short_and_placeholder_secrets(monkeypatch, env):
    _set(monkeypatch, APP_ENV=env, DATABASE_URL="postgresql://u:s3cr3t-real@h/db", ADMIN_KEY="")
    assert any("ADMIN_KEY" in e for e in config.validate())
    _set(monkeypatch, ADMIN_KEY="your-secret-admin-key-here")
    assert any("placeholder" in e for e in config.validate())
    _set(monkeypatch, ADMIN_KEY="k" * 20, DATABASE_URL="postgresql://pis_user:pis_password@h/db")
    assert any("DATABASE_URL" in e and "placeholder" in e for e in config.validate())
    _set(monkeypatch, DATABASE_URL="postgresql://u:s3cr3t-real@h/db")
    assert config.validate() == []


def test_errors_never_contain_secret_values(monkeypatch):
    _set(monkeypatch, APP_ENV="production", DATABASE_URL="postgresql://u:topsecretpw@h/db", ADMIN_KEY="short")
    assert "topsecretpw" not in " ".join(config.validate())


def test_seed_only_outside_deployed_envs(monkeypatch):
    for env, ok in [("local", True), ("test", True), ("staging", False), ("production", False)]:
        _set(monkeypatch, APP_ENV=env)
        assert config.seed_allowed() is ok


def test_admin_key_unset_disables_endpoint_even_with_empty_header(monkeypatch):
    from app.routers.admin import _require_admin
    _set(monkeypatch, ADMIN_KEY="")
    with pytest.raises(HTTPException) as e:
        _require_admin("")
    assert e.value.status_code == 503


def test_admin_key_wrong_and_right(monkeypatch):
    from app.routers.admin import _require_admin
    _set(monkeypatch, ADMIN_KEY="k" * 20)
    with pytest.raises(HTTPException) as e:
        _require_admin("nope")
    assert e.value.status_code == 403
    _require_admin("k" * 20)  # no raise
