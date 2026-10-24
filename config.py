"""Central settings. Read once from the environment (and .env); validated at API startup."""

import os

from dotenv import load_dotenv

load_dotenv()

ENVIRONMENTS = ("local", "test", "staging", "production")
APP_ENV = os.getenv("APP_ENV", "local").strip().lower()
DATABASE_URL = os.getenv("DATABASE_URL")
# Identity: tokens are issued by an external OIDC provider; the API only verifies them (RS256 via JWKS).
AUTH_ISSUER = os.getenv("AUTH_ISSUER", "")
AUTH_AUDIENCE = os.getenv("AUTH_AUDIENCE", "")
AUTH_JWKS_URL = os.getenv("AUTH_JWKS_URL", "")
AUTH_ROLE_CLAIM = os.getenv(
    "AUTH_ROLE_CLAIM", "pis_roles"
)  # list claim; "pis_operator" grants operator
MAX_BODY_BYTES = 64 * 1024
# Browser origins allowed cross-origin access (the desktop WebView). Empty = none.
CORS_ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()
]
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
# LeetCode has no official API and its terms are unverified (PRD 19#4): off until a human clears it.
LEETCODE_INTEGRATION_ENABLED = (
    os.getenv("LEETCODE_INTEGRATION_ENABLED", "false").strip().lower() == "true"
)
# Daily contribution calendar (GraphQL, needs GITHUB_TOKEN): off until the spike's open items are cleared.
GITHUB_CALENDAR_ENABLED = os.getenv("GITHUB_CALENDAR_ENABLED", "false").strip().lower() == "true"
# Second key for staging/production: a human must approve collecting daily activity there (see validate()).
GITHUB_CALENDAR_APPROVED = os.getenv("GITHUB_CALENDAR_APPROVED", "false").strip().lower() == "true"
SYNC_COOLDOWN_SECONDS = int(
    os.getenv("SYNC_COOLDOWN_SECONDS", "300")
)  # per connection, counts failed attempts too

# Values copied from .env.example / docs; never acceptable outside local/test.
_PLACEHOLDERS = ("your-secret", "your_", "changeme", "pis_password", "pis_local_dev", "<password>")


def is_deployed() -> bool:
    return APP_ENV in ("staging", "production")


def validate() -> list[str]:
    """Return human-readable configuration errors (empty list = OK). Never includes secret values."""
    errors = []
    if APP_ENV not in ENVIRONMENTS:
        errors.append(f"APP_ENV must be one of {ENVIRONMENTS}, got {APP_ENV!r}.")
    if not DATABASE_URL:
        errors.append("DATABASE_URL is not set (see .env.example).")
    if is_deployed():
        if "*" in CORS_ALLOWED_ORIGINS:
            errors.append(f"CORS_ALLOWED_ORIGINS must not contain '*' in {APP_ENV}.")
        for name, value in (
            ("AUTH_ISSUER", AUTH_ISSUER),
            ("AUTH_AUDIENCE", AUTH_AUDIENCE),
            ("AUTH_JWKS_URL", AUTH_JWKS_URL),
        ):
            if not value:
                errors.append(f"{name} must be set in {APP_ENV}.")
        if GITHUB_CALENDAR_ENABLED and not GITHUB_CALENDAR_APPROVED:
            errors.append(
                f"GITHUB_CALENDAR_ENABLED=true in {APP_ENV} also requires GITHUB_CALENDAR_APPROVED=true."
            )
        for name, value in (("DATABASE_URL", DATABASE_URL or ""),):
            if any(p in value.lower() for p in _PLACEHOLDERS):
                errors.append(
                    f"{name} looks like a placeholder/default value; set a real one for {APP_ENV}."
                )
    return errors


def seed_allowed() -> bool:
    """Demo seed data may only be loaded outside deployed environments."""
    return not is_deployed()
