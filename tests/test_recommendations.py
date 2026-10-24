"""Recommendation rules and snapshot comparison. Pure functions over hand-written fixtures (logic tests)."""

import json
from datetime import timedelta

from services.assessment import STALE_DAYS, compute_assessment
from services.recommendations import compare_results
from tests.test_assessment import NOW, _ev, _gh, _lc, _run


def _recs(ev, lc=False):
    return compute_assessment(ev, NOW, lc)["recommendations"]


def _ids(ev, lc=False):
    return [r["rule_id"] for r in _recs(ev, lc)]


def test_nothing_connected_then_connected_but_unsynced():
    assert _ids(_ev()) == ["r1.connect"]
    never = _ev(runs={"github": {"connection_status": "connected", "last_run": None}})
    assert _ids(never) == ["r2.first_sync"]


def test_failed_sync_stale_and_zero_repos():
    failed = _ev(_gh(), runs={"github": _run("failed", "rate_limited")})
    assert _ids(failed) == ["r3.sync_failed", "r3.sync_failed"]  # D1 and D2 both rest on that sync
    old = (NOW - timedelta(days=STALE_DAYS + 1)).isoformat()
    assert _ids(_ev(_gh(synced=old))) == ["r4.stale", "r4.stale"]
    g = _gh(count=0, sampled=0)
    g["values"]["commits_in_sampled_repos"] = 0
    assert "r5.no_public_repos" in _ids(_ev(g))


def test_partial_calendar_and_downward_trend():
    assert "r6.calendar_partial" in _ids(_ev(_gh(trend=None)))
    assert "r7.activity_down" in _ids(_ev(_gh(trend="down")))
    assert "r7.activity_down" not in _ids(_ev(_gh(trend="up")))


def test_leetcode_zero_only_when_enabled():
    ev = _ev(leetcode=_lc((0, 0, 0)))
    assert "r8.no_practice" in _ids(ev, lc=True) and "r8.no_practice" not in _ids(ev)


def test_cgpa_never_triggers_a_recommendation():
    assert all(r["dimension"] != "D4" for r in _recs(_ev()))
    assert "cgpa" not in json.dumps(_recs(_ev()))


def test_every_recommendation_is_traceable_ordered_and_deterministic():
    ev = _ev(_gh(trend="down", count=0, sampled=0), runs={"github": _run("failed", "x")})
    recs = _recs(ev)
    assert recs == _recs(ev) and [r["priority"] for r in recs] == list(range(1, len(recs) + 1))
    for r in recs:
        assert (
            r["rule_id"] and r["reason"] and r["action"] and r["limitation"] and r["evidence_refs"]
        )
        assert all({"dimension", "name", "sync_run_id"} <= set(ref) for ref in r["evidence_refs"])
        assert r["evidence_refs"][0]["dimension"] == r["dimension"]


def test_no_causal_or_outcome_claims():
    ev = _ev(
        _gh(trend="down", count=0, sampled=0), _lc((0, 0, 0)), runs={"github": _run("failed", "x")}
    )
    text = json.dumps(_recs(ev, lc=True)).lower()
    for phrase in (
        "will help you get",
        "increase your chances",
        "placement probability",
        "predicts",
    ):
        assert phrase not in text


def _res(**kw):
    return compute_assessment(_ev(_gh(**kw), runs={"github": _run()}), NOW)


def test_compare_differences_values_under_the_same_versions():
    c = compare_results(_res(count=2), _res(count=5, sampled=5))
    assert c["comparable"] is True
    d2 = next(d for d in c["dimensions"] if d["dimension"] == "D2")
    delta = {x["name"]: x["delta"] for x in d2["deltas"]}
    assert delta["github_public_repo_count"] == 3 and delta["repos_sampled"] == 3


def test_compare_discloses_state_changes_and_missing_dimensions():
    old = (NOW - timedelta(days=STALE_DAYS + 1)).isoformat()
    c = compare_results(_res(), compute_assessment(_ev(_gh(synced=old)), NOW))
    assert any("state changed" in n for n in c["disclosures"])
    with_lc = compute_assessment(_ev(_gh(), _lc()), NOW, leetcode_enabled=True)
    c = compare_results(_res(), with_lc)
    assert any("D3" in n and "only one" in n for n in c["disclosures"])
    assert any(d.get("only_in") == "to" for d in c["dimensions"])


def test_compare_does_not_difference_across_versions_or_missing_results():
    a, b = _res(count=2), _res(count=5, sampled=5)
    b["evidence_version"] = "evidence-v3"
    c = compare_results(a, b)
    assert c["comparable"] is False and any("not differenced" in n for n in c["disclosures"])
    assert all(x["delta"] is None for d in c["dimensions"] for x in d["deltas"])
    legacy = compare_results(None, a)
    assert legacy["comparable"] is False and legacy["dimensions"] == []
