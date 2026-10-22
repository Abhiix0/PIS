# GitHub contribution calendar spike

Run: 2026-10-19, own account `Abhiix0` only, script `experiments/spikes/github_calendar_spike.py` (committed; raw output in git-ignored `experiments/spikes/out/`). Token value never printed. "verified" = observed in a real response in this run. "unverified" = not observed.

## How to run

Own account only. Needs network and a token that can query your own `contributionsCollection`.

```bash
# set "Include private contributions" on your profile to ON, then:
GITHUB_TOKEN=... GITHUB_SPIKE_USER=<your-login> SPIKE_STATE=on  python experiments/spikes/github_calendar_spike.py
# set it to OFF, wait for GitHub to refresh, then:
GITHUB_TOKEN=... GITHUB_SPIKE_USER=<your-login> SPIKE_STATE=off python experiments/spikes/github_calendar_spike.py
```

The script reads only env (no `.env`), redacts the token from stdout and the saved JSON, and writes `experiments/spikes/out/results_<state>.json`. It probes windows of 30 to 730 days (incl. 367/370/380/390/400), timezone offsets, REST vs GraphQL for one public repo, and rate-limit headers around a rejected request. It does not probe non-default branches, forks or merge commits.

**Status of the 2026-10-22 re-run: not run.** The session that updated this script had no `GITHUB_TOKEN` or `GITHUB_SPIKE_USER`, so no new observations exist. Every row below is from the 2026-10-19 run or unverified; none of the new probes (367-390 days, rejected-request budget, ON/OFF comparison) has a result yet.

## Auth and permissions

| Item | Status | Observation |
|---|---|---|
| Existing `GITHUB_TOKEN` authenticates as `Abhiix0` | verified | GraphQL `viewer{login}` returned `Abhiix0`, HTTP 200 |
| Token OAuth scopes | verified | `X-OAuth-Scopes` header empty. The header is empty for fine-grained tokens, so the token type is not determined (unverified) |
| `contributionsCollection` works without extra scopes | verified | All queries succeeded with this token |
| Token can read private-repo data | unverified | Not tested. See private contributions below |

## Window and boundaries

| Item | Status | Observation |
|---|---|---|
| Max accepted window | verified | 365 and 366 days accepted. 400 and 730 days rejected with HTTP 200 and error `The total time spanned by 'from' and 'to' must not exceed 1 year`. Exact limit between 366 and 400 days not probed (unverified) |
| Days returned | verified | 30d window: 31 days. 365d window: 366 days (both ends inclusive). 366d window: 366 days |
| Calendar clipped to date range, not instants | verified | 366d request had `startedAt` `2025-10-18T14:10:52Z` but first calendar date `2025-10-19` |
| Date boundary and timezone | partly verified | Same March 2026 range as `Z`, `+05:30`, `-08:00`: 31, 32 and 32 days returned. `+05:30` gave `2026-02-28`..`2026-03-31` (`startedAt` `2026-02-28T18:30:00Z`). `-08:00` gave `2026-03-01`..`2026-04-01`. So the calendar covers every UTC date touched by the instants. Which timezone GitHub uses to assign a contribution to a day: unverified. Total was 117 in all three, so the extra days held no contributions or the buckets are not shifted. Per-day counts were not compared |
| Practical rule | verified (derived) | Request UTC midnight to 23:59:59Z to get exact UTC dates |

## REST comparison

| Item | Status | Observation |
|---|---|---|
| GraphQL commit count equals REST commits for one repo | verified for one repo | Repo `manasvignesh/Startupoly`, last 30 days, author `Abhiix0`: GraphQL `commitContributionsByRepository` 121, REST `/commits?author=` 121 (REST lists default branch only). One repo, one window. Not generalised |
| Non-default branches, forks, merge commits | unverified | Not tested |

## Rate limit

| Item | Status | Observation |
|---|---|---|
| Cost per call | verified | `rateLimit.cost` was 1 for each query tested. Limit 5000 per hour, `X-RateLimit-Resource: graphql` |
| Cost with larger windows | verified | Also 1 for 365d and for rejected requests (rejected 400d and 730d calls still showed `cost` 1) |
| Cost for rejected calls counted against budget | unverified | `remaining` went 4995 then 4999 across a reset, so it was not conclusive |

## Private contributions

Current state of my profile setting is not readable via the API, so the setting itself is unknown to this script.

| Window | `totalContributions` | `restrictedContributionsCount` | `hasAnyRestrictedContributions` |
|---|---|---|---|
| 30d | 368 | 0 | false |
| 365d | 1711 | 200 | true |

| Item | Status | Observation |
|---|---|---|
| Current API output for own profile | verified | As in the table above |
| Zero restricted count means no private activity | not assumed | The 30d window returned 0, the 365d window returned 200. Cause of 0 in 30d (no private activity vs. setting vs. token access) is unverified |
| Meaning of the 200 | unverified | Hypothesis: contributions to private repos the token cannot see, reported only as a count. Not confirmed |
| Setting "Include private contributions" disabled | unverified | Requires the owner to toggle it in GitHub profile settings. Not done |
| Setting enabled | unverified | Same. Not done |

Pending: owner toggles the setting, then rerun the script and record `total`, `restricted`, `hasRestricted` for each state.

## Not covered

- Users other than `Abhiix0` (by instruction).
- Hidden-private-contributions behavior for a third-party user: unverified. Expect a user viewed by someone else to expose only public counts plus a restricted count, but this was not observed.

## Terms to review (manual)

Read these yourself; no interpretation here. URLs were written from memory and not fetched; confirm they resolve.

- https://docs.github.com/en/site-policy/github-terms/github-terms-of-service (section on API terms)
- https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies
- https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement
- https://docs.github.com/en/graphql/overview/rate-limits-and-node-limits-for-the-graphql-api
- https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
- https://docs.github.com/en/account-and-profile/setting-up-and-managing-your-github-profile/managing-contribution-settings-on-your-profile/showing-your-private-contributions-and-achievements-on-your-profile
