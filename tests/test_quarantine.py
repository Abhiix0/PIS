"""The legacy RandomForest score never reaches a real-user path (DB-free)."""

import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
FORBIDDEN = re.compile(r"\bml\.predict\b|from ml import [^\n]*\bpredict\b|import ml\.predict")


def test_no_api_or_service_module_imports_the_batch_predictor():
    hits = [
        str(p.relative_to(ROOT))
        for d in ("app", "services")
        for p in (ROOT / d).rglob("*.py")
        if FORBIDDEN.search(p.read_text("utf-8"))
    ]
    assert hits == []  # ml.predict runs only from the local boot (entrypoint.sh)


def test_real_user_assessment_insert_never_sets_a_score_or_model():
    src = (ROOT / "app/routers/v1.py").read_text("utf-8")
    insert = src[src.index("INSERT INTO assessments") : src.index("RETURNING {_ASSESSMENT}")]
    assert "readiness_score" not in insert and "model_version" not in insert
    assert "'ml_readiness_proxy'" not in insert
