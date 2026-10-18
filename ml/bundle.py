"""Versioned model bundles: model + preprocessing + feature schema + target semantics move together.

A bundle is an immutable directory (models/bundles/<version>/) with a manifest of file checksums.
`model_versions` (migration 006) records its status; exactly one row is 'active'. Inference loads
only the active bundle, re-verifying checksums and schema, and refuses anything incompatible.

    python -m ml.bundle list
    python -m ml.bundle approve <version> --by <operator> [--note ...]
    python -m ml.bundle activate <version> --by <operator>     # approved or previously-active only
    python -m ml.bundle rollback --by <operator>
    python -m ml.bundle bootstrap                              # demo/first boot: activate newest passing candidate if none active
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn

from ingest.db_connection import get_connection

BUNDLES_DIR = Path("models/bundles")
FEATURE_COLS = ["cgpa", "total_problems", "avg_difficulty", "consistency_score", "commit_frequency"]
SCHEMA_VERSION = "legacy-5feature-v1"
TARGET_SEMANTICS = (
    "readiness proxy score 0-100: weighted formula of the input features plus noise "
    "(synthetic labels); NOT a placement or hiring outcome"
)
FILES = ("regressor.pkl", "classifier.pkl", "scaler.pkl", "feature_importances.json")
CATEGORIES = {"Ready", "Near Ready", "Needs Improvement"}


class BundleError(Exception):
    """Bundle missing, tampered, incompatible, or an illegal status transition."""


@dataclass
class Bundle:
    version: str
    regressor: Any
    classifier: Any
    scaler: Any
    importances: dict


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_rev() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return "unknown"


def _load(version: str, path: str, expected_sha: str) -> Bundle:
    d = Path(path)
    manifest_path = d / "manifest.json"
    if not manifest_path.exists() or _sha(manifest_path) != expected_sha:
        raise BundleError(f"{version}: manifest missing or checksum mismatch")
    m = json.loads(manifest_path.read_text())
    if m["feature_cols"] != FEATURE_COLS or m["feature_schema_version"] != SCHEMA_VERSION:
        raise BundleError(
            f"{version}: feature schema {m['feature_schema_version']} incompatible with code ({SCHEMA_VERSION})"
        )
    for name in FILES:
        if not (d / name).exists() or _sha(d / name) != m["files"].get(name):
            raise BundleError(f"{version}: {name} missing or checksum mismatch")
    b = Bundle(
        version,
        joblib.load(d / "regressor.pkl"),
        joblib.load(d / "classifier.pkl"),
        joblib.load(d / "scaler.pkl"),
        json.loads((d / "feature_importances.json").read_text()),
    )
    if list(getattr(b.scaler, "feature_names_in_", [])) != FEATURE_COLS:
        raise BundleError(f"{version}: scaler was not fitted on the expected feature order")
    for model in (b.regressor, b.classifier):
        if model.n_features_in_ != len(FEATURE_COLS):
            raise BundleError(
                f"{version}: model expects {model.n_features_in_} features, schema has {len(FEATURE_COLS)}"
            )
    return b


def smoke_test(b: Bundle) -> dict:
    """Score probe rows spanning the scaler's training range; every output must be finite and in contract."""
    lo, hi = b.scaler.data_min_, b.scaler.data_max_
    probe = pd.DataFrame(np.vstack([lo, (lo + hi) / 2, hi]), columns=FEATURE_COLS)
    x = pd.DataFrame(np.clip(b.scaler.transform(probe), 0.0, 1.0), columns=FEATURE_COLS)
    scores, cats = b.regressor.predict(x), b.classifier.predict(x)
    ok = bool(
        np.isfinite(scores).all()
        and ((scores >= 0) & (scores <= 100)).all()
        and set(map(str, cats)) <= CATEGORIES
    )
    return {
        "passed": ok,
        "probe_scores": [round(float(s), 2) for s in scores],
        "probe_categories": list(map(str, cats)),
    }


def create_candidate(src_dir: Path, metrics: dict | None = None) -> str:
    """Freeze the artifacts in src_dir into a new bundle and register it. Never activates anything."""
    files = {n: _sha(Path(src_dir) / n) for n in FILES}
    # microseconds + random suffix: identical artifacts built back-to-back must not collide
    version = (
        f"v{datetime.now(UTC):%Y%m%d%H%M%S%f}-"
        f"{hashlib.sha256(json.dumps(files).encode()).hexdigest()[:8]}-{uuid.uuid4().hex[:6]}"
    )
    dest = BUNDLES_DIR / version
    dest.mkdir(parents=True)
    for n in FILES:
        shutil.copy2(Path(src_dir) / n, dest / n)
    manifest = {
        "version": version,
        "feature_cols": FEATURE_COLS,
        "feature_schema_version": SCHEMA_VERSION,
        "target_semantics": TARGET_SEMANTICS,
        "files": files,
        "sklearn": sklearn.__version__,
        "code_revision": _git_rev(),
    }
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    sha = _sha(dest / "manifest.json")
    try:
        smoke = smoke_test(_load(version, str(dest), sha))
    except Exception as e:  # a candidate that cannot even load is recorded as rejected, not raised
        smoke = {"passed": False, "error": str(e)}
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO model_versions (version, bundle_path, bundle_sha256, feature_schema_version, feature_cols,
                   target_semantics, metrics, smoke_test, status, code_revision)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                version,
                str(dest),
                sha,
                SCHEMA_VERSION,
                json.dumps(FEATURE_COLS),
                TARGET_SEMANTICS,
                json.dumps(metrics or {}),
                json.dumps(smoke),
                "candidate" if smoke["passed"] else "rejected",
                manifest["code_revision"],
            ),
        )
    return version


def approve(version: str, by: str, note: str = "") -> None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE model_versions SET status='approved', approved_by=%s, approved_at=NOW(), approval_note=%s
               WHERE version=%s AND status='candidate' AND (smoke_test->>'passed')::boolean""",
            (by, note, version),
        )
        if cur.rowcount != 1:
            raise BundleError(f"{version} is not a candidate with a passing smoke test")


def activate(version: str, by: str) -> None:
    """Atomically make an approved (or previously active) bundle the only active one."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT bundle_path, bundle_sha256, status FROM model_versions WHERE version=%s",
            (version,),
        )
        row = cur.fetchone()
        if not row or row[2] not in ("approved", "retired"):
            raise BundleError(f"{version} is not approved")
        if not smoke_test(_load(version, row[0], row[1]))[
            "passed"
        ]:  # re-verify files right before the swap
            raise BundleError(f"{version} failed verification")
        cur.execute("UPDATE model_versions SET status='retired' WHERE status='active'")
        cur.execute(
            "UPDATE model_versions SET status='active', activated_by=%s, activated_at=NOW() WHERE version=%s",
            (by, version),
        )


def rollback(by: str) -> str:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT version FROM model_versions WHERE status='retired' ORDER BY activated_at DESC NULLS LAST LIMIT 1"
        )
        row = cur.fetchone()
    if not row:
        raise BundleError("no previous version to roll back to")
    activate(row[0], by)
    return row[0]


def list_versions() -> list[dict]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""SELECT version, status, feature_schema_version, smoke_test->>'passed', created_at,
                              approved_by, activated_at FROM model_versions ORDER BY created_at DESC""")
        keys = (
            "version",
            "status",
            "feature_schema_version",
            "smoke_passed",
            "created_at",
            "approved_by",
            "activated_at",
        )
        return [dict(zip(keys, r)) for r in cur.fetchall()]


_cache: Bundle | None = None


def load_active() -> Bundle:
    """The verified active bundle. Re-checks the registry each call so an activation or rollback takes effect
    without a restart; files are re-verified only when the active version changes."""
    global _cache
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT version, bundle_path, bundle_sha256 FROM model_versions WHERE status='active'"
        )
        row = cur.fetchone()
    if not row:
        raise BundleError("no active model version")
    if _cache is None or _cache.version != row[0]:
        _cache = _load(*row)
    return _cache


def active_version() -> str | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT version FROM model_versions WHERE status='active'")
        row = cur.fetchone()
    return row[0] if row else None


def bootstrap() -> None:
    """First-boot/demo only: with no active model, activate the newest passing candidate."""
    if active_version():
        return
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT version FROM model_versions WHERE status='candidate' ORDER BY created_at DESC LIMIT 1"
        )
        row = cur.fetchone()
    if not row:
        raise BundleError("no passing candidate to bootstrap")
    approve(row[0], "bootstrap", "first-boot activation")
    activate(row[0], "bootstrap")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["list", "approve", "activate", "rollback", "bootstrap"])
    ap.add_argument("version", nargs="?")
    ap.add_argument("--by")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    if a.cmd in ("approve", "activate", "rollback") and not a.by:
        ap.error("--by <operator> is required")
    if a.cmd == "list":
        for v in list_versions():
            print(v)
    elif a.cmd == "approve":
        approve(a.version, a.by, a.note)
    elif a.cmd == "activate":
        activate(a.version, a.by)
    elif a.cmd == "rollback":
        print("active:", rollback(a.by))
    else:
        bootstrap()
