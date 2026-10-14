"""Auth test support: a locally generated RSA key stands in for the IdP's JWKS."""
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

import config
from app import auth

ISS, AUD = "https://idp.test/", "pis-api"
_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OTHER = rsa.generate_private_key(public_exponent=65537, key_size=2048)

config.AUTH_ISSUER, config.AUTH_AUDIENCE, config.AUTH_JWKS_URL = ISS, AUD, "https://idp.test/jwks"


def make_token(sub, roles=(), exp_in=3600, iat_offset=0, key=_KEY, aud=AUD, **extra):
    now = int(time.time()) + iat_offset
    claims = {"sub": sub, "iss": ISS, "aud": aud, "iat": now, "exp": now + exp_in, config.AUTH_ROLE_CLAIM: list(roles), **extra}
    return jwt.encode(claims, key, algorithm="RS256")


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _auth_env(monkeypatch):
    monkeypatch.setattr(auth, "_signing_key", lambda token: _KEY.public_key())
    auth._buckets.clear()
