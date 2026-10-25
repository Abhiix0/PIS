"""Auth test support: a locally generated RSA key stands in for the IdP's JWKS."""

import os
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
    claims = {
        "sub": sub,
        "iss": ISS,
        "aud": aud,
        "iat": now,
        "exp": now + exp_in,
        config.AUTH_ROLE_CLAIM: list(roles),
        **extra,
    }
    return jwt.encode(claims, key, algorithm="RS256")


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _auth_env(monkeypatch):
    monkeypatch.setattr(auth, "_signing_key", lambda token: _KEY.public_key())
    auth._buckets.clear()


# ── Self-contained database ───────────────────────────────────────────
# With TEST_ADMIN_DATABASE_URL set (a role that can CREATE DATABASE), the whole session runs against a
# throwaway database: migrated, seeded, features computed, one tiny bundle trained into a tmp dir and
# activated. Nothing reads the repo's models/ or features/*.csv, and no test depends on another.
@pytest.fixture(scope="session", autouse=True)
def _test_db(tmp_path_factory):
    import uuid

    admin_url = os.getenv("TEST_ADMIN_DATABASE_URL")
    if not admin_url:
        # Never fall back to the app DATABASE_URL: DB tests would write to the real database.
        if os.getenv("PIS_TESTS_NO_DB") != "1":
            pytest.exit(
                "TEST_ADMIN_DATABASE_URL is not set. Tests need a role that can CREATE DATABASE and "
                "run on a throwaway database (use `make test` or `make test-local`, or export it, "
                "e.g. postgresql://<superuser>:<pw>@localhost:5432/postgres). "
                "DB-free subset only: PIS_TESTS_NO_DB=1.",
                returncode=2,
            )
        from ingest import db_connection

        mp = (
            pytest.MonkeyPatch()
        )  # DB-free mode: any DB access fails instead of reaching the app DB
        for mod in (config, db_connection):
            mp.setattr(mod, "DATABASE_URL", "")
        yield
        mp.undo()
        return

    import json

    import joblib
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extensions import make_dsn
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.preprocessing import MinMaxScaler

    from features.compute import load_features, run_feature_sql
    from ingest import db_connection
    from ingest.migrate import migrate
    from ml import bundle
    from ml.labels import generate_labels

    name = f"pis_test_{uuid.uuid4().hex[:10]}"
    admin = psycopg2.connect(admin_url)
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    dsn = make_dsn(admin_url, dbname=name)
    mp = pytest.MonkeyPatch()
    try:
        migrate(dsn, seed=True)
        # db_connection binds DATABASE_URL at import; repoint both.
        for mod in (config, db_connection):
            mp.setattr(mod, "DATABASE_URL", dsn)
        db_connection.close_pool()
        mp.setattr(bundle, "BUNDLES_DIR", tmp_path_factory.mktemp("bundles"))
        mp.setattr(bundle, "_cache", None)

        run_feature_sql()
        raw = load_features()
        cols = bundle.FEATURE_COLS
        scaler = MinMaxScaler().fit(raw[cols])
        scaled = raw.copy()
        scaled[cols] = scaler.transform(raw[cols])
        df = generate_labels(scaled)
        X = scaled[cols]
        src = tmp_path_factory.mktemp("train")
        reg = RandomForestRegressor(n_estimators=10, random_state=0).fit(X, df["readiness_score"])
        clf = RandomForestClassifier(n_estimators=10, random_state=0).fit(X, df["category"])
        joblib.dump(reg, src / "regressor.pkl")
        joblib.dump(clf, src / "classifier.pkl")
        joblib.dump(scaler, src / "scaler.pkl")
        (src / "feature_importances.json").write_text(
            json.dumps(
                {
                    "regressor": dict(zip(cols, reg.feature_importances_.tolist())),
                    "classifier": dict(zip(cols, clf.feature_importances_.tolist())),
                }
            )
        )
        version = bundle.create_candidate(src, {"label_origin": "synthetic_formula"})
        bundle.approve(version, "pytest", "test fixture")
        bundle.activate(version, "pytest")
        from ml.predict import predict

        for sid in raw["student_id"]:
            predict(int(sid))  # /prediction, /ranking read stored predictions
        yield dsn
    finally:
        mp.undo()
        db_connection.close_pool()
        with admin.cursor() as cur:
            cur.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
            )
        admin.close()
