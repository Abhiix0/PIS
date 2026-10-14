import numpy as np
import pandas as pd

from ml.experiment import RuleFormula, run
from ml.train import FEATURE_COLS


def _csv(tmp_path):
    rng = np.random.default_rng(0)
    df = pd.DataFrame(rng.random((12, len(FEATURE_COLS))) * 10, columns=FEATURE_COLS)
    df.insert(0, "student_id", range(12))
    p = tmp_path / "f.csv"
    df.to_csv(p, index=False)
    return p


def test_report_is_labelled_synthetic_and_reproducible(tmp_path):
    p = _csv(tmp_path)
    a, b = run(p), run(p)
    assert a["synthetic"] is True and "placement" in a["claim"]
    assert a["report_sha256"] == b["report_sha256"]
    assert {"mean", "rule_formula", "ridge", "random_forest"} <= set(a["metrics"])


def test_scaler_is_fit_inside_each_fold(tmp_path):
    # A feature far outside the training range must not be seen by the scaler fit on other folds.
    from ml.experiment import candidates
    X = pd.DataFrame(np.arange(20, dtype=float).reshape(4, 5), columns=FEATURE_COLS)
    m = candidates()["ridge"].fit(X.iloc[:3], [1, 2, 3])
    assert m[0].data_max_.max() == X.iloc[:3].to_numpy().max()


def test_rule_formula_weights():
    assert RuleFormula().predict(np.ones((1, 5)))[0] == 100
