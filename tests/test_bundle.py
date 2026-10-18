import json

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.preprocessing import MinMaxScaler

from ingest.db_connection import get_connection
from ml import bundle
from ml.bundle import FEATURE_COLS, BundleError


def _artifacts(d, n_features=len(FEATURE_COLS)):
    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.random((30, n_features)) * 10, columns=FEATURE_COLS[:n_features])
    import joblib

    scaler = MinMaxScaler().fit(X)
    Xs = pd.DataFrame(scaler.transform(X), columns=X.columns)
    y = Xs.mean(axis=1) * 100
    joblib.dump(
        RandomForestRegressor(n_estimators=5, random_state=0).fit(Xs, y), d / "regressor.pkl"
    )
    cat = np.where(y >= 65, "Ready", np.where(y >= 40, "Near Ready", "Needs Improvement"))
    joblib.dump(
        RandomForestClassifier(n_estimators=5, random_state=0).fit(Xs, cat), d / "classifier.pkl"
    )
    joblib.dump(scaler, d / "scaler.pkl")
    (d / "feature_importances.json").write_text(
        json.dumps({"regressor": dict.fromkeys(FEATURE_COLS, 0.2), "classifier": {}})
    )


@pytest.fixture
def registry(tmp_path, monkeypatch):
    """Isolated bundle dir; model_versions rows are restored afterwards."""
    monkeypatch.setattr(bundle, "BUNDLES_DIR", tmp_path / "bundles")
    monkeypatch.setattr(bundle, "_cache", None)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT version, status FROM model_versions")
        before = dict(cur.fetchall())
    yield tmp_path
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM model_versions WHERE version <> ALL(%s)", (list(before),))
        for v, s in before.items():
            cur.execute("UPDATE model_versions SET status=%s WHERE version=%s", (s, v))


def _candidate(tmp):
    src = tmp / f"src{len(list(tmp.glob('src*')))}"
    src.mkdir()
    _artifacts(src)
    return bundle.create_candidate(src)


def test_tampered_file_is_refused(registry):
    v = _candidate(registry)
    d = bundle.BUNDLES_DIR / v
    (d / "regressor.pkl").write_bytes(b"x")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT bundle_sha256 FROM model_versions WHERE version=%s", (v,))
        sha = cur.fetchone()[0]
    with pytest.raises(BundleError, match="checksum"):
        bundle._load(v, str(d), sha)


def test_incompatible_feature_schema_is_refused(registry, monkeypatch):
    v = _candidate(registry)
    monkeypatch.setattr(bundle, "SCHEMA_VERSION", "other-schema")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT bundle_path, bundle_sha256 FROM model_versions WHERE version=%s", (v,))
        path, sha = cur.fetchone()
    with pytest.raises(BundleError, match="incompatible"):
        bundle._load(v, path, sha)


def test_candidate_cannot_activate_without_approval_and_rollback_works(registry):
    first, second = _candidate(registry), _candidate(registry)
    with pytest.raises(BundleError):
        bundle.activate(first, "op")  # still a candidate
    bundle.approve(first, "op", "ok")
    bundle.activate(first, "op")
    bundle.approve(second, "op")
    bundle.activate(second, "op")
    assert bundle.active_version() == second
    assert bundle.rollback("op") == first and bundle.active_version() == first


def test_failed_activation_keeps_previous_model(registry):
    good, bad = _candidate(registry), _candidate(registry)
    bundle.approve(good, "op")
    bundle.activate(good, "op")
    bundle.approve(bad, "op")
    (bundle.BUNDLES_DIR / bad / "scaler.pkl").write_bytes(b"corrupt")
    with pytest.raises(BundleError):
        bundle.activate(bad, "op")
    assert bundle.active_version() == good


def test_rejected_candidate_cannot_be_approved(registry):
    src = registry / "bad"
    src.mkdir()
    _artifacts(src, n_features=4)  # wrong feature count for the schema
    v = bundle.create_candidate(src)
    with pytest.raises(BundleError):
        bundle.approve(v, "op")


def test_predict_records_version_snapshot_and_history_is_immutable(registry):
    from ml.predict import predict

    v = _candidate(registry)
    bundle.approve(v, "op")
    bundle.activate(v, "op")
    r = predict(1)
    assert r["model_version"] == v and r["assessment_type"] in (
        "ml_readiness_proxy",
        "insufficient_evidence",
    )
    assert (r["readiness_score"] is None) == (r["assessment_type"] == "insufficient_evidence")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT model_version, input_snapshot FROM predictions WHERE student_id=1")
        ver, snap = cur.fetchone()
        assert ver == v and snap["feature_schema_version"] == bundle.SCHEMA_VERSION
    with pytest.raises(Exception, match="immutable"):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("UPDATE prediction_history SET reason='x'")


def test_insufficient_inputs_give_no_score():
    from ml.predict import _insufficient_reason

    ok = dict.fromkeys(FEATURE_COLS, 1.0)
    assert _insufficient_reason(ok) is None
    assert "No computed features" in _insufficient_reason(None)
    assert "consistency_score" in _insufficient_reason({**ok, "consistency_score": None})
    assert "non-finite" in _insufficient_reason({**ok, "cgpa": float("nan")})
    assert "CGPA" in _insufficient_reason({**ok, "cgpa": 11.0})


def test_identical_bundles_built_back_to_back_get_distinct_versions(registry):
    src = registry / "same"
    src.mkdir()
    _artifacts(src)
    a, b = bundle.create_candidate(src), bundle.create_candidate(src)
    assert a != b and (bundle.BUNDLES_DIR / a).is_dir() and (bundle.BUNDLES_DIR / b).is_dir()
