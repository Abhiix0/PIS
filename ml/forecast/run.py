"""RQ1 forecast experiment (docs/ml/experiment-protocol.md §B): active weeks in (t, t+28d] from 12 lagged weeks.

Isolated: reads a research-export CSV (ml.forecast.export), no DB, no API route, no bundle activation.

    python -m ml.forecast.run --data <daily_*.csv> [--out experiments] [--open-test]

Validation is always evaluated. The final test is evaluated only with --open-test and only once per dataset
(a lock file in --out enforces it). Results say nothing about placement.
"""

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.linear_model import PoissonRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from ml.experiment import SEED, _git_rev

HIST_WEEKS, HORIZON_WEEKS = 12, 4
HIST_DAYS, HORIZON_DAYS = HIST_WEEKS * 7, HORIZON_WEEKS * 7
OK_STATES = {"present", "measured_zero"}  # 'stale' rows are not fresh observations
MIN_USERS_PER_PARTITION = 20  # placeholder, unverified: replace with the power calculation
BULK_DAY, BOT_RUN, BOT_MIN = 100, 7, 10  # heuristic thresholds, unverified against real accounts
BOOT = 1000
FEATURE_SCHEMA = "forecast-12w-lags-v1"
MODELS = ["persistence", "user_mean", "seasonal_naive_8w", "poisson"]
SIMPLE = MODELS[:3]


def load_daily(path: Path) -> dict[str, pd.Series]:
    """Per-user daily counts. Days absent or not in OK_STATES stay missing (never filled with 0)."""
    df = pd.read_csv(path)
    df = df[df["value_state"].isin(OK_STATES)]
    df["day"] = pd.to_datetime(df["day"])
    return {
        u: g.set_index("day")["contributions"].sort_index().astype(int)
        for u, g in df.groupby("pseudo_id")
    }


def features_as_of(daily: pd.Series, t: pd.Timestamp) -> np.ndarray:
    """12 weekly contribution sums, oldest first, from days <= t only (the single leakage choke point)."""
    h = daily.loc[t - pd.Timedelta(days=HIST_DAYS - 1) : t]
    return h.to_numpy().reshape(HIST_WEEKS, 7).sum(axis=1)


def target(daily: pd.Series, t: pd.Timestamp) -> int:
    f = daily.loc[t + pd.Timedelta(days=1) : t + pd.Timedelta(days=HORIZON_DAYS)]
    return int((f.to_numpy().reshape(HORIZON_WEEKS, 7).sum(axis=1) > 0).sum())


def _bot_like(x: np.ndarray) -> bool:
    run = best = 1
    for a, b in zip(x[:-1], x[1:], strict=True):
        run = run + 1 if (a == b and a >= BOT_MIN) else 1
        best = max(best, run)
    return len(x) > 0 and best >= BOT_RUN


def build_origins(daily: dict[str, pd.Series]) -> pd.DataFrame:
    """One row per (user, Sunday t) with every day in [t-83, t+28] observed and >=1 contribution in the 12 weeks."""
    rows = []
    for u, s in daily.items():
        for t in s.index[s.index.dayofweek == 6]:
            lo, hi = t - pd.Timedelta(days=HIST_DAYS - 1), t + pd.Timedelta(days=HORIZON_DAYS)
            win = s.loc[lo:hi]
            if (
                len(win) != HIST_DAYS + HORIZON_DAYS
                or (win.index[-1] - win.index[0]).days != len(win) - 1
            ):
                continue
            w = features_as_of(s, t)
            if w.sum() == 0:
                continue
            raw = win.to_numpy()
            rows.append(
                {
                    "user": u,
                    "t": t,
                    **{f"w{i}": int(v) for i, v in enumerate(w)},
                    "y": target(s, t),
                    "bulk": bool(raw.max() >= BULK_DAY),
                    "bot_like": _bot_like(raw),
                }
            )
    return pd.DataFrame(rows)


def split(o: pd.DataFrame, seed: int = SEED) -> tuple[dict[str, pd.DataFrame], dict]:
    """Strict: user-disjoint 60/20/20 AND time-forward with a 28-day gap. Weaker (labelled): time-forward only."""
    dates = np.sort(o["t"].unique())
    t1, t2 = dates[int(0.6 * len(dates))], dates[int(0.8 * len(dates))]
    gap = np.timedelta64(HORIZON_DAYS, "D")
    users = np.array(sorted(o["user"].unique()))
    np.random.default_rng(seed).shuffle(users)
    a, b = int(0.6 * len(users)), int(0.8 * len(users))
    groups = {"train": users[:a], "val": users[a:b], "test": users[b:]}
    time_ok = {
        "train": o["t"] + gap <= t1,  # train labels end by T1
        "val": (o["t"] > t1) & (o["t"] + gap <= t2),  # val labels end by T2, start after T1
        "test": o["t"] > t2,
    }
    strict = all(len(g) >= MIN_USERS_PER_PARTITION for g in groups.values())
    parts = {
        k: o[time_ok[k] & (o["user"].isin(groups[k]) if strict else True)].reset_index(drop=True)
        for k in time_ok
    }
    info = {
        "variant": "user_disjoint_time_forward"
        if strict
        else "WEAKER: time_forward_only_users_may_repeat",
        "T1": str(t1)[:10],
        "T2": str(t2)[:10],
        "gap_days": HORIZON_DAYS,
        "users_total": len(users),
        "min_users_per_partition": MIN_USERS_PER_PARTITION,
        "rows": {k: len(v) for k, v in parts.items()},
        "users": {k: int(v["user"].nunique()) for k, v in parts.items()},
    }
    return parts, info


def _lags(o: pd.DataFrame) -> np.ndarray:
    return o[[f"w{i}" for i in range(HIST_WEEKS)]].to_numpy()


def _active(o: pd.DataFrame) -> np.ndarray:
    return (_lags(o) > 0).astype(int)


def _clip(p) -> np.ndarray:
    return np.clip(np.rint(p), 0, HORIZON_WEEKS).astype(int)


def predict_baselines(o: pd.DataFrame) -> dict[str, np.ndarray]:
    act = _active(o)
    return {
        "persistence": act[:, -4:].sum(1),
        "user_mean": _clip(act.mean(1) * HORIZON_WEEKS),
        "seasonal_naive_8w": act[:, -8:-4].sum(1),  # same 4-week window shifted back 8 weeks
    }


def fit_poisson(train: pd.DataFrame):
    # Scaler and transform live in the pipeline, fit on train only. Fixed alpha: no tuning.
    m = make_pipeline(
        FunctionTransformer(np.log1p), StandardScaler(), PoissonRegressor(alpha=1.0, max_iter=1000)
    )
    return m.fit(_lags(train), train["y"])


def predict_all(model, o: pd.DataFrame) -> dict[str, np.ndarray]:
    return {**predict_baselines(o), "poisson": _clip(model.predict(_lags(o)))}


def _boot(o: pd.DataFrame, preds: dict[str, np.ndarray], rng) -> tuple[np.ndarray, np.ndarray]:
    """User-level bootstrap. Returns point MAE per model and BOOT x models resampled MAEs."""
    users, inv = np.unique(o["user"].to_numpy(), return_inverse=True)
    err = np.stack([np.abs(o["y"].to_numpy() - preds[m]) for m in MODELS], axis=1)
    s = np.zeros((len(users), len(MODELS)))
    np.add.at(s, inv, err)
    n = np.bincount(inv).astype(float)
    idx = rng.integers(0, len(users), (BOOT, len(users)))
    return err.mean(0), s[idx].sum(1) / n[idx].sum(1, keepdims=True)


def _ci(x) -> list[float]:
    return [round(float(v), 3) for v in np.percentile(x, [2.5, 97.5])]


def drop_to_zero(o: pd.DataFrame, pred: np.ndarray) -> dict:
    cand = predict_baselines(o)["persistence"] > 0
    event, called = cand & (o["y"].to_numpy() == 0), cand & (pred == 0)
    tp = int((event & called).sum())
    return {
        "events": int(event.sum()),
        "called": int(called.sum()),
        "true_positives": tp,
        "precision": round(tp / called.sum(), 3) if called.sum() else None,
        "recall": round(tp / event.sum(), 3) if event.sum() else None,
    }


def evaluate(o: pd.DataFrame, preds: dict[str, np.ndarray], rng) -> dict:
    if o.empty:
        return {"n": 0, "note": "no rows in this partition"}
    mae, bs = _boot(o, preds, rng)
    p = MODELS.index("persistence")
    out: dict = {"n": len(o), "users": int(o["user"].nunique()), "models": {}}
    for i, m in enumerate(MODELS):
        skill = 1 - bs[:, i] / bs[:, p] if bs[:, p].min() > 0 else None
        out["models"][m] = {
            "mae": round(float(mae[i]), 3),
            "mae_ci95_user_bootstrap": _ci(bs[:, i]),
            "skill_vs_persistence": round(1 - float(mae[i]) / float(mae[p]), 3) if mae[p] else None,
            "skill_ci95_user_bootstrap": _ci(skill) if skill is not None else None,
            "drop_to_zero": drop_to_zero(o, preds[m]),
        }
    best = min(SIMPLE, key=lambda m: mae[MODELS.index(m)])
    diff = bs[:, MODELS.index("poisson")] - bs[:, MODELS.index(best)]
    out["tree_gate"] = {
        "rule": "poisson MAE < best simple baseline with 95% user-bootstrap CI of the difference entirely below 0",
        "best_simple": best,
        "diff_ci95": _ci(diff),
        "passed": bool(np.percentile(diff, 97.5) < 0),
    }
    return out


SKILL_MIN = 0.10  # ADR 0005, owner decision 2026-10-22, pre-registered before any result exists
PROMOTION_MODEL = "poisson"  # the only candidate model; baselines are never promoted


def promotion_check(report: dict) -> dict:
    """ADR 0005 gate on the opened test set: skill >= SKILL_MIN and the lower bound of the user-level 95%
    bootstrap CI of skill > 0. Without an opened test set (or without a usable skill/CI) it is inconclusive,
    never a pass. A pass only permits proposing a bundle promotion via ml/bundle.py."""
    rule = f"skill >= {SKILL_MIN} and 95% user-bootstrap CI lower bound of skill > 0, on the opened test set"
    test = (report.get("metrics") or {}).get("test")
    m = ((test or {}).get("models") or {}).get(PROMOTION_MODEL)
    if not m:
        return {
            "status": "inconclusive",
            "rule": rule,
            "reason": "test set not opened or not evaluated",
        }
    skill, ci = m.get("skill_vs_persistence"), m.get("skill_ci95_user_bootstrap")
    if skill is None or not ci:
        return {
            "status": "inconclusive",
            "rule": rule,
            "reason": "skill or its CI is not computable",
        }
    ok = skill >= SKILL_MIN and ci[0] > 0
    return {"status": "pass" if ok else "fail", "rule": rule, "skill": skill, "ci95_lower": ci[0]}


def failure_analysis(o: pd.DataFrame, pred: np.ndarray) -> dict:
    """Worst 5% absolute errors per slice, plus bulk/bot flag rates (heuristics) among them vs overall."""
    if o.empty:
        return {}
    d = o.assign(err=np.abs(o["y"].to_numpy() - pred), pers=predict_baselines(o)["persistence"])
    d["level"] = np.where(_active(o).sum(1) <= 4, "sporadic(<=4of12)", "regular(>=5of12)")
    d["recent"] = np.where(d["pers"] > 0, "active_last4w", "inactive_last4w")
    out = {}
    for col in ("level", "recent"):
        for name, g in d.groupby(col):
            k = max(1, int(np.ceil(0.05 * len(g))))
            w = g.nlargest(k, "err")
            out[f"{col}={name}"] = {
                "n": len(g),
                "mae": round(float(g["err"].mean()), 3),
                "worst5pct_n": k,
                "worst5pct_mean_err": round(float(w["err"].mean()), 3),
                "bulk_share_worst": round(float(w["bulk"].mean()), 3),
                "bulk_share_all": round(float(g["bulk"].mean()), 3),
                "bot_like_share_worst": round(float(w["bot_like"].mean()), 3),
                "bot_like_share_all": round(float(g["bot_like"].mean()), 3),
            }
    return out


def run(data_path: Path, open_test: bool = False, out_dir: Path | None = None) -> dict:
    raw = data_path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    lock = (out_dir or Path("experiments")) / f"forecast-test-opened-{sha[:12]}.lock"
    if open_test and lock.exists():
        raise SystemExit(f"Final test already opened for this dataset ({lock}). It is opened once.")
    origins = build_origins(load_daily(data_path))
    body: dict = {
        "claim": "Forecast of next-4-week GitHub active weeks for consenting users. No placement claim.",
        "dataset": {"path": data_path.as_posix(), "sha256": sha, "origins": len(origins)},
        "feature_schema_version": FEATURE_SCHEMA,
        "seed": SEED,
        "code_revision": _git_rev(),
        "runtime": {
            "python": sys.version.split()[0],
            "sklearn": sklearn.__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
    }
    if origins.empty:
        body["result"] = (
            "NO ORIGINS: no user has 12 observed history weeks + 4 observed future weeks. Nothing evaluated."
        )
    else:
        parts, info = split(origins)
        body["split"] = info
        rng = np.random.default_rng(SEED)
        if parts["train"].empty:
            body["result"] = "EMPTY TRAIN PARTITION: nothing fit, nothing evaluated."
        else:
            model = fit_poisson(parts["train"])
            body["poisson_params"] = model[-1].get_params()
            names = ["val"] + (["test"] if open_test else [])
            body["metrics"], body["failure_analysis"] = {}, {}
            for k in names:
                preds = predict_all(model, parts[k]) if len(parts[k]) else {}
                body["metrics"][k] = evaluate(parts[k], preds, rng)
                best = (
                    min(MODELS, key=lambda m: body["metrics"][k]["models"][m]["mae"])
                    if preds
                    else None
                )
                if best:
                    body["failure_analysis"][k] = {
                        "model": best,
                        "slices": failure_analysis(parts[k], preds[best]),
                    }
            body["test_opened"] = open_test
            body["tree_model"] = (
                "not run (no tree model unless the gate passes on validation; none implemented)"
            )
    body["promotion_check"] = promotion_check(body)
    body["report_sha256"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, default=str).encode()
    ).hexdigest()
    if open_test and "metrics" in body:
        lock.parent.mkdir(exist_ok=True)
        lock.write_text(body["report_sha256"])
    return body


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", type=Path)
    ap.add_argument("--out", default="experiments", type=Path)
    ap.add_argument("--open-test", action="store_true")
    ap.add_argument(
        "--check", type=Path, help="apply the promotion gate to a saved report and exit"
    )
    a = ap.parse_args(argv)
    if a.check:
        print(json.dumps(promotion_check(json.loads(a.check.read_text())), indent=2))
        return 0
    if not a.data:
        ap.error("--data is required unless --check is given")
    rep = run(a.data, a.open_test, a.out)
    a.out.mkdir(exist_ok=True)
    path = a.out / f"forecast-{rep['dataset']['sha256'][:12]}.json"
    path.write_text(json.dumps(rep, indent=2, default=str))
    print(f"Forecast report: {path}")
    for k, m in rep.get("metrics", {}).items():
        print(k, {n: (v["mae"], v["skill_vs_persistence"]) for n, v in m.get("models", {}).items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
