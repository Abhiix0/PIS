"""Token verification and server-side authorization. The IdP issues tokens; this module only verifies them."""

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer

import config
from ingest.db_connection import get_connection

OPERATOR_ROLE = "pis_operator"
_bearer = HTTPBearer(auto_error=False)

# shortcut: in-process sliding window, per worker; move to a shared store (Redis/gateway) when running >1 API replica.
_buckets: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def _hit(key: str, limit: int, window: int) -> bool:
    """Record a hit; False when `key` exceeded `limit` hits in the last `window` seconds."""
    now = time.monotonic()
    with _lock:
        q = _buckets[key]
        while q and q[0] <= now - window:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True


def rate_limit(name: str, limit: int, window: int = 60):
    """Dependency factory: per-caller (token subject if known, else client IP) limit for `name`."""

    def dep(request: Request):
        who = getattr(request.state, "rl_subject", None) or (
            request.client.host if request.client else "?"
        )
        if not _hit(f"{name}:{who}", limit, window):
            raise HTTPException(status_code=429, detail="Too many requests")

    return dep


expensive = rate_limit("expensive", 10)


@dataclass(frozen=True)
class Principal:
    user_id: str
    subject: str
    is_operator: bool


@lru_cache(maxsize=1)
def _jwks_client():
    return jwt.PyJWKClient(config.AUTH_JWKS_URL, cache_keys=True)


def _signing_key(token: str):  # seam for tests
    return _jwks_client().get_signing_key_from_jwt(token).key


def _load_user(subject: str, email: str | None) -> dict:
    """Get-or-create the users row for an IdP subject."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (auth_subject, email) VALUES (%s, %s)
                ON CONFLICT (auth_subject) DO UPDATE SET auth_subject = EXCLUDED.auth_subject
                RETURNING id::text, status, sessions_valid_after
            """,
                (subject, email),
            )
            uid, status, valid_after = cur.fetchone()
    return {"id": uid, "status": status, "valid_after": valid_after}


def _reject(ip: str, detail: str = "Not authenticated"):
    # Bounded retries for bad credentials per client IP.
    if not _hit(f"authfail:{ip}", 20, 60):
        raise HTTPException(status_code=429, detail="Too many failed attempts")
    raise HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def current_principal(request: Request, creds=Depends(_bearer)) -> Principal:
    ip = request.client.host if request.client else "?"
    if creds is None or not (config.AUTH_ISSUER and config.AUTH_AUDIENCE and config.AUTH_JWKS_URL):
        _reject(ip)  # unconfigured auth fails closed
    try:
        token = creds.credentials
        claims = jwt.decode(
            token,
            _signing_key(token),
            algorithms=["RS256"],
            audience=config.AUTH_AUDIENCE,
            issuer=config.AUTH_ISSUER,
            options={"require": ["exp", "iat", "sub"]},
        )
    except (
        Exception
    ):  # expired, bad signature, wrong aud/iss, JWKS failure: indistinguishable to the caller
        _reject(ip)
    user = _load_user(claims["sub"], claims.get("email"))
    if user["status"] != "active":
        raise HTTPException(status_code=403, detail="Account not active")
    if user["valid_after"] and claims["iat"] < user["valid_after"].timestamp():
        _reject(ip, "Session revoked")
    request.state.rl_subject = claims["sub"]
    roles = claims.get(config.AUTH_ROLE_CLAIM) or []
    return Principal(user["id"], claims["sub"], OPERATOR_ROLE in roles)


def require_operator(p: Principal = Depends(current_principal)) -> Principal:
    if not p.is_operator:
        raise HTTPException(status_code=403, detail="Operator role required")
    return p
