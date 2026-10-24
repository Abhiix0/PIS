"""Deterministic preparation assessment (rules-v1). Pure functions of a stored evidence snapshot and a clock.

No model, no score, no composite: one object per dimension with an evidence state, the values behind it,
the rule that produced the state, a coverage line and caveats. Every threshold below is "proposed, unvalidated"
(docs/architecture/intelligence-spec.md §4).
"""

from datetime import UTC, datetime

from services.recommendations import recommend

ASSESSMENT_VERSION = "rules-v1"
STALE_DAYS = 7  # proposed, unvalidated: a provider import older than this is "stale"
RESULT_TYPE = "rules_assessment"  # assessments.assessment_type when any provider dimension has data
LIMITATIONS = (
    "A preparation assessment summarises public activity evidence. It is not a score and does not estimate "
    "hiring or placement outcomes. Private work, other platforms and skill are not observed."
)

STATES = ("no_evidence", "stale", "partial", "sufficient", "source_failed")

_COVERAGE = {
    "D1": "Public GitHub contribution calendar, last 12 weeks, as visible to a public profile.",
    "D2": "Public GitHub, newest 10 non-fork repositories, commits authored by the username.",
    "D3": "LeetCode accepted-problem counts by difficulty at fetch time (unofficial source).",
    "D4": "Self-reported CGPA from your profile. Context only; never counted as evidence.",
}
_CAVEATS = {
    "D1": [
        "Counts commits, issues, pull requests and reviews, not skill, code quality, effort or hours.",
        "Private work is undercounted or invisible; how GitHub assigns days to a timezone is unverified.",
        "Says nothing about hiring or placement.",
    ],
    "D2": [
        "Commit recency is unknown: the date used is the repository's last push, not a commit date.",
        "Commits under emails not linked to the account are excluded; private repositories are invisible.",
        "Not a measure of project quality.",
    ],
    "D3": [
        "Solve dates are unknown, so no consistency or trend can be stated.",
        "Not problem-solving ability or interview performance.",
    ],
    "D4": [
        "Self-reported: not verified and not comparable across institutions or scales.",
        "Not used in any other dimension or recommendation.",
    ],
}
_RULES = {
    "D1": (
        "d1.activity_trend.v1",
        "Active weeks (any contribution) in the last 4 weeks versus the previous 8, per-week rate. "
        "Needs all 12 weeks of calendar days; otherwise no direction is stated.",
    ),
    "D2": (
        "d2.project_footprint.v1",
        "Counts of public repositories and of commits in the sampled repositories; partial when "
        "repositories exceed the sample.",
    ),
    "D3": (
        "d3.leetcode_volume.v1",
        "Accepted problems by difficulty; the total is shown only when all three counts exist.",
    ),
    "D4": ("d4.cgpa_context.v1", "Shows the entered CGPA as self-reported context."),
}
_TITLES = {
    "D1": "GitHub activity consistency",
    "D2": "GitHub project footprint",
    "D3": "LeetCode practice volume",
    "D4": "Academic context",
}


def _value(name, value, provenance, state, meta, block):
    m = meta.get(name, {})
    return {
        "name": name,
        "value": value,
        "provenance": provenance,
        "value_state": "not_collected" if value is None else state,
        "event_at_precision": m.get("event_at_precision"),
        "collected_at": m.get("collected_at"),
        "synced_at": block["synced_at"] if block else None,
        "sync_run_id": block["sync_run_id"] if block else None,
    }


def _stale(block, now) -> bool:
    return (now - datetime.fromisoformat(block["synced_at"])).days >= STALE_DAYS


def _state(block, run, has_data: bool, partial: bool, now) -> str:
    if run and run["status"] == "failed":  # last attempt failed; last-known-good values stay listed
        return "source_failed"
    if block is None or not has_data:
        return "no_evidence"
    if _stale(block, now):
        return "stale"
    if partial or (run and run["status"] == "partial"):
        return "partial"
    return "sufficient"


def _dimension(did, state, values, notes=None, run=None):
    rule_id, rule_text = _RULES[did]
    out = {
        "dimension": did,
        "title": _TITLES[did],
        "evidence_state": state,
        "values": values,
        "rule": {"id": rule_id, "text": rule_text},
        "coverage": _COVERAGE[did],
        "caveats": list(_CAVEATS[did]) + (notes or []),
    }
    if run and run["status"] in ("failed", "partial"):
        out["last_sync"] = {"status": run["status"], "error_code": run.get("safe_error_code")}
    return out


def _d1(ev, run, now):
    b = ev.get("github")
    trend = b and b.get("activity_trend")
    if not trend:
        notes = (
            ["The daily calendar has not been collected, so no activity consistency can be stated."]
            if b
            else []
        )
        return _dimension("D1", _state(b, run, False, False, now), [], notes, run)
    meta, prov = b.get("value_meta", {}), "derived"
    names = ("active_weeks_last_4", "active_weeks_prev_8")
    values = [_value(n, b["values"].get(n), prov, "present", meta, b) for n in names]
    values.append(_value("trend_direction", trend["direction"], prov, "present", meta, b))
    incomplete = trend["direction"] is None
    notes = (
        ["Fewer than 12 full weeks of calendar days: no direction is stated."] if incomplete else []
    )
    return _dimension("D1", _state(b, run, True, incomplete, now), values, notes, run)


def _d2(ev, run, now):
    b = ev.get("github")
    v = (b or {}).get("values", {})
    names = ("github_public_repo_count", "commits_in_sampled_repos", "repos_sampled")
    if not b or v.get("github_public_repo_count") is None:
        return _dimension("D2", _state(b, run, False, False, now), [], None, run)
    states = b.get("value_states", {})
    values = [
        _value(n, v.get(n), b["provenance"], states.get(n, "present"), b.get("value_meta", {}), b)
        for n in names
        if n in v
    ]
    capped = v["github_public_repo_count"] > v.get("repos_sampled", 0)
    notes = (
        ["More public repositories than the sample covers; the footprint is truncated."]
        if capped
        else []
    )
    return _dimension("D2", _state(b, run, True, capped, now), values, notes, run)


def _d3(ev, run, now):
    b = ev.get("leetcode")
    v = (b or {}).get("values", {})
    names = (
        "leetcode_solved_easy",
        "leetcode_solved_medium",
        "leetcode_solved_hard",
        "leetcode_solved_all",
    )
    present = [n for n in names if v.get(n) is not None]
    if not b or not present:
        return _dimension("D3", _state(b, run, False, False, now), [], None, run)
    states, meta = b.get("value_states", {}), b.get("value_meta", {})
    values = [
        _value(
            n,
            v[n],
            "derived" if n in b.get("derived", []) else b["provenance"],
            states.get(n, "present"),
            meta,
            b,
        )
        for n in present
    ]
    missing = "leetcode_solved_all" not in v
    notes = (
        ["A difficulty count is missing, so no total is shown (missing is not zero)."]
        if missing
        else []
    )
    return _dimension("D3", _state(b, run, True, missing, now), values, notes, run)


def _d4(ev):
    c = ev.get("cgpa")
    values = (
        [
            {
                "name": "cgpa",
                "value": c["value"],
                "provenance": c["provenance"],
                "value_state": "present",
                "event_at_precision": None,
                "collected_at": None,
                "synced_at": None,
                "sync_run_id": None,
            }
        ]
        if c
        else []
    )
    return _dimension("D4", "sufficient" if c else "no_evidence", values)


def compute_assessment(
    ev: dict, now: datetime | None = None, leetcode_enabled: bool = False
) -> dict:
    """Same evidence and clock give the same output. `ev` is an evidence-v2 snapshot (app/routers/v1.py)."""
    now = now or datetime.now(UTC)
    if any((ev.get(k) or {}).get("provenance") == "synthetic" for k in ("github", "leetcode")):
        raise ValueError("synthetic data must never reach a real-user assessment")
    runs = ev.get("runs") or {}
    dims = [
        _d1(ev, (runs.get("github") or {}).get("last_run"), now),
        _d2(ev, (runs.get("github") or {}).get("last_run"), now),
    ]
    if leetcode_enabled:
        dims.append(_d3(ev, (runs.get("leetcode") or {}).get("last_run"), now))
    dims.append(_d4(ev))
    return {
        "assessment_version": ASSESSMENT_VERSION,
        "evidence_version": ev.get("evidence_version"),
        "generated_at": now.isoformat(),
        "stale_after_days": STALE_DAYS,
        "dimensions": dims,
        "recommendations": recommend(ev, dims, STALE_DAYS),
        "limitations": LIMITATIONS,
    }


def has_provider_evidence(result: dict) -> bool:
    """True when at least one provider dimension (not the CGPA context) has values to show."""
    return any(d["values"] for d in result["dimensions"] if d["dimension"] != "D4")
