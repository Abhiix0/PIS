"""Traceable recommendations and snapshot comparison over rules-v1 results. Pure functions, no model.

Every recommendation names its rule id, the dimension/value it came from and the sync run behind it. Thresholds are
named constants, proposed and unvalidated (docs/architecture/intelligence-spec.md §4).
"""

RECOMMENDATION_LIMITATION = (
    "Based only on the public activity summarised here. Nothing shows that acting on it changes any "
    "hiring or placement outcome."
)
TREND_DOWN = "down"  # proposed, unvalidated: the D1 direction that triggers r7


def _ref(dim, name=None):
    run = next((v["sync_run_id"] for v in dim["values"] if v["sync_run_id"]), None)
    return {"dimension": dim["dimension"], "name": name, "sync_run_id": run}


def _val(dim, name):
    return next((v["value"] for v in dim["values"] if v["name"] == name), None)


def recommend(ev: dict, dims: list[dict], stale_days: int) -> list[dict]:
    """Rules in fixed priority order. CGPA (D4) is context only and never triggers a recommendation."""
    by = {d["dimension"]: d for d in dims}
    runs = ev.get("runs") or {}
    providers = [d for d in dims if d["dimension"] != "D4"]
    any_values = any(d["values"] for d in providers)
    d1, d2, d3 = by["D1"], by["D2"], by.get("D3")  # D3 exists only when LeetCode is enabled
    recs: list[tuple[str, dict, str, str, list]] = []

    if not any_values and not any(runs.get(p) for p in ("github", "leetcode")):
        recs.append(
            (
                "r1.connect",
                d1,
                "Connect your GitHub username and run a sync.",
                "No provider is connected, so there is no evidence to review.",
                [_ref(d1)],
            )
        )
    elif not any_values and not any(d["evidence_state"] == "source_failed" for d in providers):
        recs.append(
            (
                "r2.first_sync",
                d1,
                "Run a sync for your connected account.",
                "An account is connected but no data has been imported yet.",
                [_ref(d1)],
            )
        )
    for d in providers:
        if d["evidence_state"] == "source_failed":
            code = (d.get("last_sync") or {}).get("error_code") or "unknown"
            reason = f"The last sync for {d['title']} failed (code: {code})."
            recs.append(("r3.sync_failed", d, "Retry the sync later.", reason, [_ref(d)]))
        elif d["evidence_state"] == "stale":
            reason = f"The last import for {d['title']} is {stale_days} or more days old."
            recs.append(("r4.stale", d, "Re-sync to refresh this data.", reason, [_ref(d)]))
    if _val(d2, "github_public_repo_count") == 0:
        recs.append(
            (
                "r5.no_public_repos",
                d2,
                "Publish a project to a public repository.",
                "The provider reported 0 public repositories, so no public project work is visible.",
                [_ref(d2, "github_public_repo_count")],
            )
        )
    if d1["evidence_state"] == "partial":
        recs.append(
            (
                "r6.calendar_partial",
                d1,
                "Sync again later; the activity trend needs 12 full weeks of calendar data.",
                "The calendar does not yet cover 12 full weeks, so no trend is stated.",
                [_ref(d1, "trend_direction")],
            )
        )
    if _val(d1, "trend_direction") == TREND_DOWN:
        recs.append(
            (
                "r7.activity_down",
                d1,
                "Pick a small recurring time slot for projects or practice if this change was not intended.",
                "Active weeks in the last 4 weeks are fewer (per week) than in the previous 8.",
                [_ref(d1, "active_weeks_last_4"), _ref(d1, "active_weeks_prev_8")],
            )
        )
    if d3 and _val(d3, "leetcode_solved_all") == 0:
        recs.append(
            (
                "r8.no_practice",
                d3,
                "Solve a few practice problems.",
                "The provider reported 0 solved problems.",
                [_ref(d3, "leetcode_solved_all")],
            )
        )
    return [
        {
            "id": f"rec-{i}-{rule_id.split('.')[0]}",
            "rule_id": rule_id,
            "priority": i,
            "dimension": dim["dimension"],
            "action": action,
            "reason": reason,
            "evidence_refs": refs,
            "limitation": RECOMMENDATION_LIMITATION,
        }
        for i, (rule_id, dim, action, reason, refs) in enumerate(recs, 1)
    ]


def _versions(r):
    return r["assessment_version"], r["evidence_version"]


def compare_results(a: dict | None, b: dict | None) -> dict:
    """`a` is the earlier snapshot, `b` the later. Values are differenced only under identical versions."""
    if not a or not b:
        return {
            "comparable": False,
            "disclosures": ["A snapshot has no rules result."],
            "dimensions": [],
        }
    same = _versions(a) == _versions(b)
    notes: list[str] = []
    if not same:
        notes.append(
            "Versions differ ({}/{} vs {}/{}): values are not differenced.".format(
                *_versions(a), *_versions(b)
            )
        )
    da, db = ({d["dimension"]: d for d in r["dimensions"]} for r in (a, b))
    out = []
    for did in sorted(set(da) | set(db)):
        x, y = da.get(did), db.get(did)
        if not x or not y:
            notes.append(f"{did} is present in only one snapshot.")
            out.append({"dimension": did, "only_in": "from" if x else "to", "deltas": []})
            continue
        if x["evidence_state"] != y["evidence_state"]:
            notes.append(
                f"{did} evidence state changed: {x['evidence_state']} to {y['evidence_state']}."
            )
        vx, vy = ({v["name"]: v["value"] for v in d["values"]} for d in (x, y))
        deltas = []
        for name in sorted(set(vx) | set(vy)):
            f, t = vx.get(name), vy.get(name)
            delta = (
                t - f
                if same and isinstance(f, int | float) and isinstance(t, int | float)
                else None
            )
            deltas.append({"name": name, "from": f, "to": t, "delta": delta})
        out.append(
            {
                "dimension": did,
                "from_state": x["evidence_state"],
                "to_state": y["evidence_state"],
                "deltas": deltas,
            }
        )
    return {"comparable": same, "disclosures": notes, "dimensions": out}
