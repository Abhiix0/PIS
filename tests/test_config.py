"""Config validation — no DB needed."""
import pytest

import config


def _set(monkeypatch, **kw):
    for k, v in kw.items():
        monkeypatch.setattr(config, k, v)


def test_local_requires_only_database_url(monkeypatch):
    _set(monkeypatch, APP_ENV="local", DATABASE_URL="postgresql://u:x@h/db")
    assert config.validate() == []
    _set(monkeypatch, DATABASE_URL=None)
    assert any("DATABASE_URL" in e for e in config.validate())


def test_unknown_env_rejected(monkeypatch):
    _set(monkeypatch, APP_ENV="prod", DATABASE_URL="postgresql://u:x@h/db")
    assert any("APP_ENV" in e for e in config.validate())


@pytest.mark.parametrize("env", ["staging", "production"])
def test_deployed_rejects_missing_auth_and_placeholder_secrets(monkeypatch, env):
    _set(monkeypatch, APP_ENV=env, DATABASE_URL="postgresql://u:s3cr3t-real@h/db",
         AUTH_ISSUER="", AUTH_AUDIENCE="", AUTH_JWKS_URL="")
    errs = " ".join(config.validate())
    assert all(n in errs for n in ("AUTH_ISSUER", "AUTH_AUDIENCE", "AUTH_JWKS_URL"))
    _set(monkeypatch, AUTH_ISSUER="https://idp.example/", AUTH_AUDIENCE="pis", AUTH_JWKS_URL="https://idp.example/jwks",
         DATABASE_URL="postgresql://pis_user:pis_password@h/db")
    assert any("DATABASE_URL" in e and "placeholder" in e for e in config.validate())
    _set(monkeypatch, DATABASE_URL="postgresql://u:s3cr3t-real@h/db")
    assert config.validate() == []


def test_errors_never_contain_secret_values(monkeypatch):
    _set(monkeypatch, APP_ENV="production", DATABASE_URL="postgresql://u:topsecretpw@h/db")
    assert "topsecretpw" not in " ".join(config.validate())


def test_seed_only_outside_deployed_envs(monkeypatch):
    for env, ok in [("local", True), ("test", True), ("staging", False), ("production", False)]:
        _set(monkeypatch, APP_ENV=env)
        assert config.seed_allowed() is ok
