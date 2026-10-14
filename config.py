"""Central settings. Read once from the environment (and .env); validated at API startup."""
import os
from dotenv import load_dotenv

load_dotenv()

ENVIRONMENTS = ("local", "test", "staging", "production")
APP_ENV = os.getenv("APP_ENV", "local").strip().lower()
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_KEY = os.getenv("ADMIN_KEY", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

MIN_ADMIN_KEY_LEN = 16
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
        if len(ADMIN_KEY) < MIN_ADMIN_KEY_LEN:
            errors.append(f"ADMIN_KEY must be set and at least {MIN_ADMIN_KEY_LEN} characters in {APP_ENV}.")
        for name, value in (("ADMIN_KEY", ADMIN_KEY), ("DATABASE_URL", DATABASE_URL or "")):
            if any(p in value.lower() for p in _PLACEHOLDERS):
                errors.append(f"{name} looks like a placeholder/default value; set a real one for {APP_ENV}.")
    return errors


def seed_allowed() -> bool:
    """Demo seed data may only be loaded outside deployed environments."""
    return not is_deployed()
