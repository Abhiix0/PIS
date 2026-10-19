"""Operator-only research export of daily GitHub contribution observations (never an API route).

    python -m ml.forecast.export --out <dir> --i-understand-this-exports-research-data

Includes only users whose `research_consent_at` is set at run time, `provenance='observed'` rows, and the newest
collected value per (profile, day). Past exports are files outside the database: revoking consent cannot recall them.
"""

import argparse
import csv
import hashlib
import json
import secrets
import sys
from datetime import UTC, datetime
from pathlib import Path

from ingest.db_connection import get_connection
from services.privacy import audit

CONFIRM_FLAG = "--i-understand-this-exports-research-data"
COLUMNS = ["pseudo_id", "day", "contributions", "value_state"]

_SQL = """
SELECT DISTINCT ON (p.id, o.event_at) p.user_id::text AS user_id, o.event_at::date AS day,
       o.value_num::int AS contributions, o.value_state::text AS value_state
FROM source_observations o
JOIN profiles p ON p.id = o.profile_id
JOIN users u ON u.id = p.user_id
WHERE u.research_consent_at IS NOT NULL AND u.status <> 'deleted'
  AND o.provenance = 'observed' AND o.observation_type = 'github_contribution_day'
  AND o.event_at IS NOT NULL AND o.quality_status <> 'rejected'
ORDER BY p.id, o.event_at, o.collected_at DESC
"""


def run(out_dir: Path) -> dict:
    salt = secrets.token_hex(
        16
    )  # per export, never written out: ids cannot be linked across exports
    export_id = secrets.token_hex(8)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(_SQL)
        rows = cur.fetchall()
        pseudo = lambda uid: hashlib.sha256(f"{salt}:{uid}".encode()).hexdigest()[:16]  # noqa: E731
        data = sorted((pseudo(uid), str(day), n, st) for uid, day, n, st in rows)
        out_dir.mkdir(parents=True, exist_ok=True)
        csv_path = out_dir / f"daily_{export_id}.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(COLUMNS)
            w.writerows(data)
        manifest = {
            "export_id": export_id,
            "created_at": datetime.now(UTC).isoformat(),
            "file": csv_path.name,
            "data_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
            "rows": len(data),
            "users": len({d[0] for d in data}),
            "columns": COLUMNS,
        }
        (out_dir / f"manifest_{export_id}.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        audit(
            cur, "research_export.created", target=export_id
        )  # export id only, no personal values
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument(CONFIRM_FLAG, dest="confirmed", action="store_true")
    args = ap.parse_args(argv)
    if not args.confirmed:
        print(f"Refusing to export: pass {CONFIRM_FLAG} to confirm.", file=sys.stderr)
        return 2
    print(json.dumps(run(args.out), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
