"""Throwaway spike: GitHub GraphQL contributionCalendar, own account only.
Run: GITHUB_TOKEN=... GITHUB_SPIKE_USER=<login> [SPIKE_STATE=on|off] python experiments/spikes/github_calendar_spike.py
Reads env only. Raw JSON goes to experiments/spikes/out/ (git-ignored). Token is redacted from all output."""
import json, os, sys, pathlib, datetime as dt
import requests

OUT = pathlib.Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)
tok = os.environ.get("GITHUB_TOKEN")
user = os.environ.get("GITHUB_SPIKE_USER")
state = os.environ.get("SPIKE_STATE", "unlabelled")  # private-contributions setting you set by hand: on|off
if not tok or not user:
    sys.exit("need GITHUB_TOKEN and GITHUB_SPIKE_USER in env")

def redact(x):
    return str(x).replace(tok, "***")

_print = print
print = lambda *a, **k: _print(*[redact(i) for i in a], **k)
H = {"Authorization": f"Bearer {tok}"}
Q = """query($u:String!,$f:DateTime!,$t:DateTime!){
 rateLimit{cost remaining limit resetAt}
 user(login:$u){contributionsCollection(from:$f,to:$t){
  startedAt endedAt restrictedContributionsCount hasAnyRestrictedContributions
  totalCommitContributions
  commitContributionsByRepository(maxRepositories:10){repository{nameWithOwner isPrivate} contributions{totalCount}}
  contributionCalendar{totalContributions weeks{contributionDays{date contributionCount weekday}}}}}}"""

def gql(f, t):
    try:
        r = requests.post("https://api.github.com/graphql", headers=H, timeout=30,
                          json={"query": Q, "variables": {"u": user, "f": f, "t": t}})
    except requests.RequestException as e:
        sys.exit(redact(f"network failure: {type(e).__name__}"))
    hdr = {k: v for k, v in r.headers.items() if k.lower().startswith("x-ratelimit")}
    return r.status_code, r.json(), hdr

def days(j):
    cc = j["data"]["user"]["contributionsCollection"]
    return [d for w in cc["contributionCalendar"]["weeks"] for d in w["contributionDays"]], cc

now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
iso = lambda d: d.strftime("%Y-%m-%dT%H:%M:%SZ")
res = {}
# 1. window sweep
for n in (30, 365, 366, 367, 370, 380, 390, 400, 730):
    st, j, h = gql(iso(now - dt.timedelta(days=n)), iso(now))
    ok = "errors" not in j and j.get("data", {}).get("user")
    row = {"status": st, "ok": bool(ok), "headers": h, "rateLimit": j.get("data", {}).get("rateLimit") if j.get("data") else None}
    if ok:
        d, cc = days(j)
        row.update(days=len(d), first=d[0]["date"], last=d[-1]["date"], total=cc["contributionCalendar"]["totalContributions"],
                   started=cc["startedAt"], ended=cc["endedAt"], restricted=cc["restrictedContributionsCount"],
                   hasRestricted=cc["hasAnyRestrictedContributions"])
    else:
        row["errors"] = [e.get("message") for e in j.get("errors", [])][:2]
    res[f"window_{n}d"] = row
    print(f"window {n}d:", {k: v for k, v in row.items() if k not in ("headers",)})
# 1b. do rejected requests consume budget? valid, rejected, valid: compare remaining
seq = []
for n in (30, 730, 30):
    _, j, h = gql(iso(now - dt.timedelta(days=n)), iso(now))
    seq.append({"days": n, "remaining_header": h.get("x-ratelimit-remaining"), "used_header": h.get("x-ratelimit-used")})
res["rejected_budget"] = seq
print("rejected_budget", seq)
# 2. boundary / tz: same instants expressed with offsets
for label, f, t in (("utc", "2026-03-01T00:00:00Z", "2026-03-31T23:59:59Z"),
                    ("plus0530", "2026-03-01T00:00:00+05:30", "2026-03-31T23:59:59+05:30"),
                    ("minus0800", "2026-03-01T00:00:00-08:00", "2026-03-31T23:59:59-08:00")):
    st, j, h = gql(f, t)
    if "errors" in j or not j["data"]["user"]:
        print("boundary", label, "error", [e.get("message") for e in j.get("errors", [])][:1]); continue
    d, cc = days(j)
    res[f"boundary_{label}"] = {"days": len(d), "first": d[0]["date"], "last": d[-1]["date"], "started": cc["startedAt"], "ended": cc["endedAt"], "total": cc["contributionCalendar"]["totalContributions"]}
    print("boundary", label, res[f"boundary_{label}"])
# 3. REST vs GraphQL for top repo over last 30d
f, t = iso(now - dt.timedelta(days=30)), iso(now)
st, j, h = gql(f, t)
cc = j["data"]["user"]["contributionsCollection"]
pub = [r for r in cc["commitContributionsByRepository"] if not r["repository"]["isPrivate"]]
if pub:
    repo = pub[0]["repository"]["nameWithOwner"]; gq = pub[0]["contributions"]["totalCount"]; n = 0; page = 1
    while True:
        r = requests.get(f"https://api.github.com/repos/{repo}/commits", headers=H, timeout=30,
                         params={"author": user, "since": f, "until": t, "per_page": 100, "page": page})
        if r.status_code != 200:
            print("REST error", r.status_code); break
        n += len(r.json()); page += 1
        if len(r.json()) < 100: break
    res["rest_vs_graphql"] = {"repo": repo, "graphql_commit_contribs": gq, "rest_commits_default_branch": n}
    print("rest_vs_graphql", res["rest_vs_graphql"])
else:
    print("no public repo with commits in last 30d; REST comparison not possible")
res["_run"] = {"state": state, "utc": iso(now)}
(OUT / f"results_{state}.json").write_text(redact(json.dumps(res, indent=1)))
print(f"saved experiments/spikes/out/results_{state}.json")
