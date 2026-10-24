"""Forecast experiment: leakage, split disjointness, test-once. Fixtures are generated in-test (no real data)."""

import json

import numpy as np
import pandas as pd
import pytest

from ml.forecast import run as fr


def _series(seed, days=400, start="2025-01-06"):  # 2025-01-06 is a Monday
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=days)
    return pd.Series(rng.poisson(rng.uniform(0.1, 2), days), index=idx)


def _origins(n_users=120):
    return fr.build_origins({f"u{i}": _series(i) for i in range(n_users)})


def test_features_ignore_future_and_target_ignores_past():
    s = _series(1)
    t = s.index[s.index.dayofweek == 6][20]
    f, y = fr.features_as_of(s, t), fr.target(s, t)
    fut, past = s.copy(), s.copy()
    fut.loc[t + pd.Timedelta(days=1) :] += 50
    past.loc[: t - pd.Timedelta(days=1)] = 0
    assert (fr.features_as_of(fut, t) == f).all()  # future edits never reach features
    assert fr.target(past, t) == y  # past edits never reach the label
    assert fr.target(fut, t) != y or y == 4


def test_missing_days_are_not_origins():
    s = _series(2)
    t = s.index[s.index.dayofweek == 6][20]
    full = len(fr.build_origins({"a": s}))
    gap = s.drop(t + pd.Timedelta(days=3))
    assert len(fr.build_origins({"a": gap})) < full  # a missing day is not filled with 0


def test_strict_split_disjoint_and_forward():
    parts, info = fr.split(_origins())
    assert info["variant"] == "user_disjoint_time_forward"
    u = {k: set(v["user"]) for k, v in parts.items()}
    assert (
        not (u["train"] & u["val"]) and not (u["train"] & u["test"]) and not (u["val"] & u["test"])
    )
    gap = pd.Timedelta(days=28)
    assert parts["train"]["t"].max() + gap <= pd.Timestamp(info["T1"])
    assert parts["val"]["t"].min() > pd.Timestamp(info["T1"])
    assert parts["val"]["t"].max() + gap <= pd.Timestamp(info["T2"])
    assert parts["test"]["t"].min() > pd.Timestamp(info["T2"])


def test_small_n_falls_back_and_is_labelled():
    parts, info = fr.split(_origins(n_users=6))
    assert info["variant"].startswith("WEAKER")
    assert parts["train"]["t"].max() < parts["test"]["t"].min()


def test_test_opens_once(tmp_path):
    csv = tmp_path / "d.csv"
    rows = []
    for i in range(60):
        s = _series(i)
        rows += [(f"u{i}", str(d.date()), int(v), "present") for d, v in s.items()]
    pd.DataFrame(rows, columns=["pseudo_id", "day", "contributions", "value_state"]).to_csv(
        csv, index=False
    )
    rep = fr.run(csv, open_test=False, out_dir=tmp_path)
    assert "test" not in rep["metrics"] and set(rep["metrics"]["val"]["models"]) == set(fr.MODELS)
    fr.run(csv, open_test=True, out_dir=tmp_path)
    with pytest.raises(SystemExit):
        fr.run(csv, open_test=True, out_dir=tmp_path)
    assert fr.run(csv, out_dir=tmp_path)["report_sha256"] == rep["report_sha256"]  # reproducible


def test_drop_to_zero_counts():
    o = pd.DataFrame(
        {
            **{f"w{i}": [0, 0] for i in range(8)},
            **{f"w{i}": [1, 1] for i in range(8, 12)},
            "y": [0, 0],
        }
    )
    d = fr.drop_to_zero(o, np.array([0, 2]))
    assert (d["events"], d["called"], d["precision"], d["recall"]) == (2, 1, 1.0, 0.5)


def test_failure_analysis_and_cli(tmp_path, capsys):
    o = _origins(n_users=20)
    fa = fr.failure_analysis(o, fr.predict_baselines(o)["persistence"])
    assert all(v["worst5pct_n"] >= 1 for v in fa.values())
    csv = tmp_path / "d.csv"
    rows = [
        (f"u{i}", str(d.date()), int(v), "present")
        for i in range(30)
        for d, v in _series(i).items()
    ]
    pd.DataFrame(rows, columns=["pseudo_id", "day", "contributions", "value_state"]).to_csv(
        csv, index=False
    )
    assert fr.main(["--data", str(csv), "--out", str(tmp_path)]) == 0
    assert list(tmp_path.glob("forecast-*.json"))


def _report(skill, ci, opened=True):
    m = {"models": {"poisson": {"skill_vs_persistence": skill, "skill_ci95_user_bootstrap": ci}}}
    return {"metrics": {"val": m, **({"test": m} if opened else {})}}


def test_promotion_check_pass_fail_and_inconclusive():
    assert fr.promotion_check(_report(0.12, [0.03, 0.2]))["status"] == "pass"
    assert (
        fr.promotion_check(_report(0.10, [0.01, 0.2]))["status"] == "pass"
    )  # boundary is inclusive
    assert fr.promotion_check(_report(0.08, [0.01, 0.2]))["status"] == "fail"  # skill too small
    assert fr.promotion_check(_report(0.12, [-0.01, 0.2]))["status"] == "fail"  # CI includes 0
    assert (
        fr.promotion_check(_report(0.12, [0.0, 0.2]))["status"] == "fail"
    )  # lower bound must be > 0
    # a strong validation result never counts: the test set must have been opened
    assert fr.promotion_check(_report(0.5, [0.4, 0.6], opened=False))["status"] == "inconclusive"
    assert fr.promotion_check({})["status"] == "inconclusive"
    assert fr.promotion_check(_report(None, None))["status"] == "inconclusive"


def test_reports_carry_the_check_and_the_cli_applies_it(tmp_path, capsys):
    rep = tmp_path / "r.json"
    rep.write_text(json.dumps(_report(0.2, [0.1, 0.3])))
    assert fr.main(["--check", str(rep)]) == 0
    assert '"status": "pass"' in capsys.readouterr().out
