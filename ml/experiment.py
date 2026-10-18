"""Reproducible baseline experiment runner (Phase 7).

Runs ONLY on the committed synthetic demo dataset. The target is the constructed
formula label from ml/labels.py, so results measure how well a model re-learns
that formula, not any placement outcome. Output is a pipeline smoke test.

    python -m ml.experiment [--features features/features_raw.csv] [--out experiments]
"""

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import MinMaxScaler

from ml.labels import _LABEL_NOISE_SEED, _LABEL_NOISE_STD, WEIGHTS, generate_labels
from ml.train import FEATURE_COLS

SEED = 42
FEATURE_SCHEMA = "legacy-5feature-v1"
TARGET = "readiness_score: weighted formula of min-max scaled features + N(0, 5) noise (synthetic)"


class RuleFormula(BaseEstimator, RegressorMixin):
    """Transparent baseline: the label weights applied to scaled features, no learning."""

    def fit(self, X, y=None):
        self.n_features_in_ = np.asarray(X).shape[1]
        return self

    def predict(self, X):
        return np.asarray(X) @ np.array([WEIGHTS[c] for c in FEATURE_COLS])


def candidates():
    # Scaler sits inside each pipeline, so it is fit on the training fold only.
    return {
        "mean": make_pipeline(DummyRegressor(strategy="mean")),
        "rule_formula": make_pipeline(MinMaxScaler(), RuleFormula()),
        "ridge": make_pipeline(MinMaxScaler(), Ridge(alpha=1.0)),
        "random_forest": make_pipeline(
            MinMaxScaler(), RandomForestRegressor(n_estimators=100, random_state=SEED)
        ),
    }


def _bootstrap_ci(err, rng, n=1000):
    # shortcut: percentile bootstrap over students, very wide at n~8; replace with a power-based design.
    means = [err[rng.integers(0, len(err), len(err))].mean() for _ in range(n)]
    return [round(float(np.percentile(means, 2.5)), 3), round(float(np.percentile(means, 97.5)), 3)]


def _git_rev():
    try:
        rev = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip())
        return f"{rev}{'+dirty' if dirty else ''}"
    except Exception:
        return "unknown"


def run(features_path: Path) -> dict:
    raw_bytes = features_path.read_bytes()
    df = pd.read_csv(features_path)
    # Target: labels need full-dataset scaling, so they are fixed before splitting (part of the target definition).
    scaled = df.copy()
    scaled[FEATURE_COLS] = MinMaxScaler().fit_transform(df[FEATURE_COLS])
    y = generate_labels(scaled)["readiness_score"].to_numpy()
    X, groups = df[FEATURE_COLS], df["student_id"]
    # One row per student today; group splits keep that true if repeated rows are added later.
    n_splits = groups.nunique()
    cv = GroupKFold(n_splits=n_splits)
    rng = np.random.default_rng(SEED)
    metrics = {}
    for name, model in candidates().items():
        pred = cross_val_predict(model, X, y, groups=groups, cv=cv)
        abs_err = np.abs(y - pred)
        metrics[name] = {
            "mae": round(float(abs_err.mean()), 3),
            "mae_ci95_bootstrap": _bootstrap_ci(abs_err, rng),
            "rmse": round(float(np.sqrt(((y - pred) ** 2).mean())), 3),
            "params": model[-1].get_params(),
        }
    base = metrics["mean"]["mae"]
    for m in metrics.values():
        m["skill_vs_mean"] = round(1 - m["mae"] / base, 3)
    body = {
        "synthetic": True,
        "claim": "Pipeline smoke test on synthetic formula labels. Says nothing about placement outcomes.",
        "dataset": {
            "path": str(features_path),
            "sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "rows": len(df),
            "students": int(n_splits),
            "origin": "seed.sql demo students",
        },
        "feature_schema_version": FEATURE_SCHEMA,
        "features": FEATURE_COLS,
        "target": TARGET,
        "label_noise": {"std": _LABEL_NOISE_STD, "seed": _LABEL_NOISE_SEED},
        "split": f"GroupKFold(n_splits={n_splits}) by student_id (leave-one-student-out); "
        "no untouched final test set: n is too small to hold one out",
        "seed": SEED,
        "code_revision": _git_rev(),
        "runtime": {
            "python": sys.version.split()[0],
            "sklearn": sklearn.__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "metrics": metrics,
    }
    body["report_sha256"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, default=str).encode()
    ).hexdigest()
    return body


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", default="features/features_raw.csv")
    ap.add_argument("--out", default="experiments")
    a = ap.parse_args()
    report = run(Path(a.features))
    out = Path(a.out)
    out.mkdir(exist_ok=True)
    path = out / f"baseline-synthetic-{report['dataset']['sha256'][:12]}.json"
    path.write_text(json.dumps(report, indent=2, default=str))
    print(f"SYNTHETIC smoke test, no placement claim. Report: {path}")
    for k, m in report["metrics"].items():
        print(
            f"  {k:<14} MAE {m['mae']:>7}  CI {m['mae_ci95_bootstrap']}  skill {m['skill_vs_mean']}"
        )
