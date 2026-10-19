import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { FEATURE_DEFS, compare, priorities } from "../lib/assessment";
import Integrations, { describeRun } from "./Integrations";
import Overview from "./Overview";

afterEach(() => vi.unstubAllGlobals());
const json = (b: unknown, status = 200) => Response.json(b, { status });
const A = (id: string, t: string, extra = {}) => ({
  id,
  assessment_type: "insufficient_evidence",
  readiness_score: null,
  category: null,
  reason: "No score for real accounts.",
  model_version: null,
  created_at: t,
  ...extra,
});
const gh = (n: number, at = new Date().toISOString()) => ({
  sync_run_id: "r1",
  synced_at: at,
  provenance: "observed",
  values: { github_public_repo_count: n },
});
const ev = (o = {}) => ({ evidence_version: "evidence-v1", cgpa: null, github: null, leetcode: null, ...o });

it("derives priorities from evidence and never invents any", () => {
  expect(priorities(ev()).map((p) => p.id)).toEqual(["connect", "cgpa"]);
  const old = new Date(Date.now() - 30 * 864e5).toISOString();
  const ids = priorities(ev({ cgpa: { value: 8, provenance: "user_entered" }, github: gh(0, old) })).map(
    (p) => p.id,
  );
  expect(ids).toEqual(["stale-github", "repos"]);
});

it("refuses to compare different evidence versions and discloses coverage changes", () => {
  const a = { a: A("1", "t1") as never, ev: ev() };
  expect(compare(a, { a: a.a, ev: { ...ev(), evidence_version: "evidence-v2" } }).comparable).toBe(false);
  const c = compare(a, { a: a.a, ev: ev({ github: gh(3) }) as never });
  expect(c.comparable).toBe(true);
  expect(c.notes.join()).toMatch(/github data is present in only one/);
  expect(c.deltas).toEqual([{ key: "github_public_repo_count", from: null, to: 3 }]);
});

it("defines the activity-trend evidence keys", () => {
  expect(FEATURE_DEFS.active_weeks_last_4).toMatch(/last 4/);
  expect(FEATURE_DEFS.active_weeks_prev_8).toMatch(/8 before/);
});

it("distinguishes provider outcomes", () => {
  const run = { id: "1", provider: "github", completed_at: null, records_created: 0, records_rejected: 0 };
  expect(describeRun({ ...run, status: "failed", safe_error_code: "rate_limited" })).toMatch(/rate-limiting/);
  expect(describeRun({ ...run, status: "failed", safe_error_code: "unavailable" })).toMatch(/outage/);
  expect(describeRun({ ...run, status: "failed", safe_error_code: "forbidden" })).toMatch(/refused access/);
  expect(describeRun({ ...run, status: "partial", safe_error_code: "partial_result" })).toMatch(/partly/);
});

it("overview shows no score for an insufficient-evidence snapshot, and says why", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) =>
      url.includes("/evidence")
        ? json({ assessment_id: "1", evidence: ev({ github: gh(2) }) })
        : json({ items: [A("1", new Date().toISOString())] }),
    ),
  );
  render(<Overview />);
  expect(await screen.findByText(/No score yet. No score for real accounts./)).toBeInTheDocument();
  expect(screen.queryByText(/Readiness proxy score/)).toBeNull();
});

it("overview offers retry when the backend is down", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("down")));
  render(<Overview />);
  expect(await screen.findByRole("alert")).toHaveTextContent(/cannot reach the server/i);
});

it("connect needs explicit consent, then sends the username", async () => {
  const f = vi.fn(async (_url: string, init?: RequestInit) =>
    init?.method === "PUT" ? json({ id: "c" }) : json({ items: [] }),
  );
  vi.stubGlobal("fetch", f);
  render(<Integrations />);
  await userEvent.type((await screen.findAllByLabelText("GitHub username"))[0]!, "octo");
  const btn = screen.getAllByText("Connect")[0]!;
  expect(btn).toBeDisabled();
  await userEvent.click(screen.getAllByRole("checkbox")[0]!);
  await userEvent.click(btn);
  const put = f.mock.calls.find((c) => c[1]?.method === "PUT")!;
  expect(put[0]).toMatch(/integrations\/github$/);
  expect(JSON.parse(put[1]!.body as string)).toEqual({ username: "octo" });
});
