"""rules-v1 golden fixtures. Pure functions: no DB. Fixtures are hand-written evidence-v2 snapshots (logic tests, not real data)."""

import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from services.assessment import (
    ASSESSMENT_VERSION,
    STALE_DAYS,
    compute_assessment,
    has_provider_evidence,
)

NOW = datetime(2024, 6, 30, 12, tzinfo=UTC)
FRESH = (NOW - timedelta(days=1)).isoformat()
META = {"event_at_precision": "repo_push", "collected_at": FRESH}


def _gh(synced=FRESH, trend="up", count=2, sampled=2):
    values = {
        "github_public_repo_count": count,
        "commits_in_sampled_repos": 7,
        "repos_sampled": sampled,
        "active_weeks_last_4": 4 if trend else None,
        "active_weeks_prev_8": 0 if trend else None,
    }
    return {
        "sync_run_id": "r1",
        "synced_at": synced,
        "provenance": "observed",
        "values": values,
        "value_states": {
            "github_public_repo_count": "present",
            "commits_in_sampled_repos": "present",
        },
        "value_meta": {k: META for k in values},
        "derived": [],
        "activity_trend": {"direction": trend, "rule": "x", "as_of": "2024-06-29"},
    }


def _lc(solved=(5, 0, 1)):
    names = ("leetcode_solved_easy", "leetcode_solved_medium", "leetcode_solved_hard")
    values = dict(zip(names, solved))
    values["leetcode_solved_all"] = sum(solved)
    states = {k: "present" for k in values} | {"leetcode_solved_medium": "measured_zero"}
    return {
        "sync_run_id": "r2",
        "synced_at": FRESH,
        "provenance": "observed",
        "values": values,
        "value_states": states,
        "value_meta": {k: {"event_at_precision": "unknown", "collected_at": FRESH} for k in values},
        "derived": ["leetcode_solved_all"],
    }


def _ev(github=None, leetcode=None, cgpa=None, runs=None):
    return {
        "evidence_version": "evidence-v2",
        "cgpa": cgpa,
        "github": github,
        "leetcode": leetcode,
        "runs": runs or {},
    }


def _run(status="succeeded", code=None):
    last = {"id": "r", "status": status, "safe_error_code": code}
    return {"connection_status": "connected", "last_run": last}


def _states(ev, lc=False):
    dims = compute_assessment(ev, NOW, lc)["dimensions"]
    return {d["dimension"]: d["evidence_state"] for d in dims}


def test_not_connected_and_never_synced_are_no_evidence():
    assert _states(_ev()) == {"D1": "no_evidence", "D2": "no_evidence", "D4": "no_evidence"}
    never = _ev(runs={"github": {"connection_status": "connected", "last_run": None}})
    assert _states(never)["D1"] == "no_evidence"
    assert not has_provider_evidence(compute_assessment(never, NOW))


def test_failed_sync_is_source_failed_and_keeps_last_known_good():
    r = compute_assessment(_ev(_gh(), runs={"github": _run("failed", "rate_limited")}), NOW)
    d1, d2 = r["dimensions"][0], r["dimensions"][1]
    assert d1["evidence_state"] == d2["evidence_state"] == "source_failed"
    assert d1["last_sync"] == {"status": "failed", "error_code": "rate_limited"} and d2["values"]
    only_failed = compute_assessment(_ev(runs={"github": _run("failed", "not_found")}), NOW)
    assert only_failed["dimensions"][0]["evidence_state"] == "source_failed"
    assert not has_provider_evidence(only_failed)


def test_stale_after_the_proposed_window():
    old = (NOW - timedelta(days=STALE_DAYS)).isoformat()
    assert _states(_ev(_gh(synced=old)))["D2"] == "stale"
    recent = (NOW - timedelta(days=STALE_DAYS - 1)).isoformat()
    assert _states(_ev(_gh(synced=recent)))["D2"] == "sufficient"


def test_partial_calendar_has_no_direction_and_says_so():
    d1 = compute_assessment(_ev(_gh(trend=None)), NOW)["dimensions"][0]
    assert d1["evidence_state"] == "partial"
    direction = next(v for v in d1["values"] if v["name"] == "trend_direction")
    assert direction["value"] is None and direction["value_state"] == "not_collected"
    assert any("12 full weeks" in c for c in d1["caveats"])


def test_partial_run_and_repo_cap_are_partial():
    assert _states(_ev(_gh(), runs={"github": _run("partial")}))["D2"] == "partial"
    assert _states(_ev(_gh(count=14, sampled=10)))["D2"] == "partial"


def test_github_without_calendar_has_no_d1_but_has_d2():
    g = _gh()
    del g["activity_trend"]
    s = _states(_ev(g))
    assert s["D1"] == "no_evidence" and s["D2"] == "sufficient"


def test_measured_zero_is_kept_as_a_reported_zero():
    g = _gh(count=0, sampled=0)
    g["values"]["commits_in_sampled_repos"] = 0
    g["value_states"] = {
        "github_public_repo_count": "measured_zero",
        "commits_in_sampled_repos": "measured_zero",
    }
    d2 = compute_assessment(_ev(g), NOW)["dimensions"][1]
    zero = next(v for v in d2["values"] if v["name"] == "github_public_repo_count")
    assert zero["value"] == 0 and zero["value_state"] == "measured_zero"
    assert d2["evidence_state"] == "sufficient"


def test_full_evidence_every_dimension_carries_its_trail():
    cgpa = {"value": 8.1, "provenance": "user_entered"}
    ev = _ev(_gh(), _lc(), cgpa, {"github": _run(), "leetcode": _run()})
    r = compute_assessment(ev, NOW, leetcode_enabled=True)
    assert r["assessment_version"] == ASSESSMENT_VERSION and r["evidence_version"] == "evidence-v2"
    assert [d["dimension"] for d in r["dimensions"]] == ["D1", "D2", "D3", "D4"]
    for d in r["dimensions"]:
        assert d["evidence_state"] == "sufficient" and d["values"]
        assert d["rule"]["id"] and d["rule"]["text"] and d["coverage"] and d["caveats"]
        for v in d["values"]:
            assert v["provenance"] and "sync_run_id" in v and "synced_at" in v
    d3 = r["dimensions"][2]
    total = next(v for v in d3["values"] if v["name"] == "leetcode_solved_all")
    assert total["value"] == 6 and total["provenance"] == "derived"
    medium = next(v for v in d3["values"] if v["name"] == "leetcode_solved_medium")
    assert medium["value_state"] == "measured_zero"


def test_leetcode_dimension_only_when_enabled_and_total_needs_all_three():
    assert "D3" not in _states(_ev(leetcode=_lc()))
    lc = _lc()
    del lc["values"]["leetcode_solved_all"], lc["values"]["leetcode_solved_hard"]
    assert _states(_ev(leetcode=lc), lc=True)["D3"] == "partial"


def test_cgpa_is_context_only():
    ev = _ev(cgpa={"value": 9.0, "provenance": "user_entered"})
    r = compute_assessment(ev, NOW)
    assert r["dimensions"][-1]["dimension"] == "D4" and not has_provider_evidence(r)
    assert "cgpa" not in json.dumps([d for d in r["dimensions"] if d["dimension"] != "D4"])


def test_same_input_same_output_and_input_is_not_mutated():
    ev = _ev(_gh(), cgpa={"value": 7.0, "provenance": "user_entered"}, runs={"github": _run()})
    before = deepcopy(ev)
    assert compute_assessment(ev, NOW) == compute_assessment(ev, NOW) and ev == before


def test_no_score_and_no_forbidden_wording():
    cgpa = {"value": 8.1, "provenance": "user_entered"}
    text = json.dumps(compute_assessment(_ev(_gh(), _lc(), cgpa, {"github": _run()}), NOW, True))
    for phrase in (
        "placement probability",
        "chance of getting placed",
        "predicts",
        "readiness_score",
        "composite",
    ):
        assert phrase not in text.lower()


def test_synthetic_evidence_is_refused():
    g = _gh()
    g["provenance"] = "synthetic"
    with pytest.raises(ValueError):
        compute_assessment(_ev(g), NOW)
