import re
from collections import Counter

from ingest.migrate import MIGRATIONS_DIR, migration_files

# Applied before the unique-prefix rule; renaming would break schema_migrations history.
GRANDFATHERED = ["001_add_github_unique.sql", "001_add_usernames.sql"]


def _names():
    return [p.name for p in migration_files(MIGRATIONS_DIR)]


def test_names_are_three_digit_prefixed():
    bad = [n for n in _names() if not re.fullmatch(r"\d{3}_[a-z0-9_]+\.sql", n)]
    assert not bad, bad


def test_order_is_deterministic():
    names = _names()
    assert names == sorted(names)
    assert names.index(GRANDFATHERED[0]) + 1 == names.index(GRANDFATHERED[1])


def test_prefixes_unique_except_grandfathered():
    counts = Counter(n[:3] for n in _names() if n not in GRANDFATHERED)
    assert [p for p, c in counts.items() if c > 1] == []
    assert "001" not in counts, "new migration reused grandfathered prefix 001"
