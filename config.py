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
AUTH_ROLE_CLAIM = os.getenv("AUTH_ROLE_CLAIM", "pis_roles")  # list claim; "pis_operator" grants operator
MAX_BODY_BYTES = 64 * 1024
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

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
        for name, value in (("AUTH_ISSUER", AUTH_ISSUER), ("AUTH_AUDIENCE", AUTH_AUDIENCE), ("AUTH_JWKS_URL", AUTH_JWKS_URL)):
            if not value:
                errors.append(f"{name} must be set in {APP_ENV}.")
        for name, value in (("DATABASE_URL", DATABASE_URL or ""),):
            if any(p in value.lower() for p in _PLACEHOLDERS):
                errors.append(f"{name} looks like a placeholder/default value; set a real one for {APP_ENV}.")
    return errors


def seed_allowed() -> bool:
    """Demo seed data may only be loaded outside deployed environments."""
    return not is_deployed()
