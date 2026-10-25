// Dev-only fetch stub (VITE_MOCK_API=1). Imported dynamically behind import.meta.env.DEV, so prod bundles drop it.
// URL flags: #signed-out (sign-in screen), ?mock=empty|error|slow (state sets).
import type { Native } from "../auth/native";
import { API_BASE_URL } from "./client";
import type { DimensionValue } from "./v1";

const day = 864e5;
const ago = (d: number) => new Date(Date.now() - d * day).toISOString();
const flag = new URLSearchParams(location.search).get("mock");

const profile = {
  id: "p1",
  display_name: "Ada Lovelace",
  branch: "Computer Science",
  graduation_year: 2027,
  cgpa: 8.4,
};
const integrations = [
  {
    id: "i1",
    provider: "github",
    external_username: "ada-codes",
    status: "active",
    last_attempt_at: ago(2),
    last_success_at: ago(2),
  },
  {
    id: "i2",
    provider: "leetcode",
    external_username: "ada_lc",
    status: "active",
    last_attempt_at: ago(12),
    last_success_at: ago(12),
  },
];
// Sample data only. Shapes and field names follow the server's rules-v1 contract (services/assessment.py).
type State = "no_evidence" | "stale" | "partial" | "sufficient" | "source_failed";
const val = (name: string, value: number | string | null, d: number, run: string): DimensionValue => ({
  name,
  value,
  provenance: "observed",
  value_state: value === null ? "not_collected" : value === 0 ? "measured_zero" : "present",
  event_at_precision: "repo_push",
  collected_at: ago(d),
  synced_at: ago(d),
  sync_run_id: run,
});
const dim = (
  dimension: string,
  title: string,
  evidence_state: State,
  values: DimensionValue[],
  rule_id: string,
  rule: string,
  coverage: string,
  caveats: string[],
  last_sync?: { status: string; error_code: string | null },
) => ({
  dimension,
  title,
  evidence_state,
  values,
  rule: { id: rule_id, text: rule },
  coverage,
  caveats,
  ...(last_sync ? { last_sync } : {}),
});
const result = (repos: number, kind: "full" | "failed" | "none") => {
  const none = kind === "none";
  const d1v = none
    ? []
    : [
        val("active_weeks_last_4", 3, 2, "11111111-aaaa"),
        val("active_weeks_prev_8", 5, 2, "11111111-aaaa"),
        val("trend_direction", kind === "full" ? "down" : null, 2, "11111111-aaaa"),
      ];
  const d2v = none
    ? []
    : [
        val("github_public_repo_count", repos, 2, "11111111-aaaa"),
        val("commits_in_sampled_repos", repos * 11, 2, "11111111-aaaa"),
        val("repos_sampled", Math.min(repos, 10), 2, "11111111-aaaa"),
      ];
  const d3v = none ? [] : [val("leetcode_solved_all", 0, 12, "22222222-bbbb")];
  const dimensions = [
    dim(
      "D1",
      "GitHub activity consistency",
      none ? "no_evidence" : kind === "failed" ? "source_failed" : "partial",
      d1v,
      "d1.activity_trend.v1",
      "Active weeks, last 4 versus previous 8.",
      "Public GitHub contribution calendar, last 12 weeks.",
      ["Counts contributions, not skill or effort.", "Says nothing about hiring or placement."],
      kind === "failed" ? { status: "failed", error_code: "rate_limited" } : undefined,
    ),
    dim(
      "D2",
      "GitHub project footprint",
      none ? "no_evidence" : "sufficient",
      d2v,
      "d2.project_footprint.v1",
      "Counts of public repositories and sampled commits.",
      "Public GitHub, newest 10 non-fork repositories.",
      ["Commit dates are repository push dates.", "Not a measure of project quality."],
    ),
    dim(
      "D3",
      "LeetCode practice volume",
      none ? "no_evidence" : "stale",
      d3v,
      "d3.leetcode_volume.v1",
      "Accepted problems by difficulty.",
      "LeetCode counts at fetch time (unofficial source).",
      ["Solve dates are unknown."],
    ),
    dim(
      "D4",
      "Academic context",
      "sufficient",
      [
        {
          ...val("cgpa", 8.4, 0, "x"),
          provenance: "user_entered",
          sync_run_id: null,
          synced_at: null,
          collected_at: null,
          event_at_precision: null,
          value_state: "present",
        },
      ],
      "d4.cgpa_context.v1",
      "Shows the entered CGPA as self-reported context.",
      "Self-reported CGPA from your profile.",
      ["Not verified; never counted as evidence."],
    ),
  ];
  const recommendations = none
    ? [
        {
          id: "rec-1-r1",
          rule_id: "r1.connect",
          priority: 1,
          dimension: "D1",
          action: "Connect your GitHub username and run a sync.",
          reason: "No provider is connected, so there is no evidence to review.",
          evidence_refs: [{ dimension: "D1", name: null, sync_run_id: null }],
          limitation: "Based only on the public activity summarised here.",
        },
      ]
    : [
        {
          id: "rec-1-r4",
          rule_id: "r4.stale",
          priority: 1,
          dimension: "D3",
          action: "Re-sync to refresh this data.",
          reason: "The last import for LeetCode practice volume is 7 or more days old.",
          evidence_refs: [{ dimension: "D3", name: null, sync_run_id: "22222222-bbbb" }],
          limitation: "Based only on the public activity summarised here.",
        },
      ];
  return {
    assessment_version: "rules-v1",
    evidence_version: "evidence-v2",
    generated_at: ago(0),
    stale_after_days: 7,
    dimensions,
    recommendations,
    limitations:
      "A preparation assessment summarises public activity evidence. It is not a score and does not estimate hiring or placement outcomes.",
  };
};
const A = (id: string, d: number, kind: "full" | "failed" | "none", repos: number) => ({
  id,
  assessment_type: kind === "none" ? "insufficient_evidence" : "rules_assessment",
  readiness_score: null,
  category: null,
  reason:
    kind === "none"
      ? "No synced provider data yet. Connect an account and run a sync."
      : "Per-dimension evidence states from fixed rules (rules-v1). There is no score.",
  model_version: null,
  result: result(repos, kind),
  created_at: ago(d),
});
const assessments = [A("a3", 1, "full", 14), A("a2", 9, "failed", 11), A("a1", 20, "none", 0)];
const run = {
  id: "r1",
  provider: "github",
  status: "succeeded",
  completed_at: ago(0),
  records_created: 14,
  records_rejected: 0,
  safe_error_code: null,
};

const json = (b: unknown, status = 200) => Response.json(b, { status });
function compareMock(x: string, y: string) {
  const [a, b] = [x, y].map((id) => assessments.find((i) => i.id === id)!);
  const dims = (a!.result.dimensions ?? []).map((d) => {
    const o = b!.result.dimensions.find((e) => e.dimension === d.dimension)!;
    return {
      dimension: d.dimension,
      from_state: d.evidence_state,
      to_state: o.evidence_state,
      deltas: d.values.map((v) => {
        const t = o.values.find((w) => w.name === v.name)?.value ?? null;
        const delta = typeof v.value === "number" && typeof t === "number" ? t - v.value : null;
        return { name: v.name, from: v.value, to: t, delta };
      }),
    };
  });
  return {
    from: { id: a!.id, created_at: a!.created_at },
    to: { id: b!.id, created_at: b!.created_at },
    comparable: true,
    disclosures: ["Sample data."],
    dimensions: dims,
  };
}

function route(path: string, method: string): Response | Promise<Response> {
  if (path === "/health") return json({ status: "ok", version: "mock" });
  if (flag === "error" && path.startsWith("/api/v1"))
    return json(
      {
        error: {
          code: "internal",
          message: "The mock server is failing on purpose.",
          request_id: "mock-0001",
        },
      },
      500,
    );
  const empty = flag === "empty";
  if (path === "/api/v1/me") return json({ user_id: "u1", profile: empty ? null : profile });
  if (path === "/api/v1/me/profile") return json(profile);
  if (path === "/api/v1/me/privacy") return json({ research_consent: false });
  if (path === "/api/v1/me/export") return json({ profile, integrations });
  if (path === "/api/v1/integrations") return json({ items: empty ? [] : integrations });
  if (path.endsWith("/sync")) return json({ id: "r1" }, 202);
  if (path.startsWith("/api/v1/sync-runs/")) return json(run);
  if (path.startsWith("/api/v1/sync-runs")) return json({ items: [run] });
  if (path.startsWith("/api/v1/assessments")) {
    if (method === "POST") return json(assessments[0]!, 201);
    const m = /assessments\/(\w+)\/compare\/(\w+)/.exec(path);
    if (m) return json(compareMock(m[1]!, m[2]!));
    return json({ items: empty ? [] : assessments });
  }
  return json({ error: { code: "not_found", message: "No mock for this route.", request_id: "mock" } }, 404);
}

export function installMock() {
  const real = window.fetch.bind(window);
  window.fetch = async (input, init) => {
    const u = new URL(
      typeof input === "string" ? input : input instanceof URL ? input.href : input.url,
      location.href,
    );
    if (u.host === "mock.idp")
      // OIDC stand-in so the normal session code path runs unchanged
      return u.pathname.endsWith("oauth-authorization-server")
        ? json({ issuer: "http://mock.idp", authorization_endpoint: "http://mock.idp/auth", token_endpoint: "http://mock.idp/token" })
        : json({ access_token: "mock", expires_in: 3600, refresh_token: "mock" });
    if (u.origin !== new URL(API_BASE_URL).origin) return real(input, init);
    if (flag === "slow") await new Promise((r) => setTimeout(r, 60_000));
    return route(u.pathname + u.search, (init?.method ?? "GET").toUpperCase());
  };
}

export const mockNative: Native = {
  loadRefresh: async () => (location.hash === "#signed-out" ? null : "mock"),
  saveRefresh: async () => {},
  clearRefresh: async () => {},
  listen: async () => 0,
  waitCallback: () => new Promise(() => {}),
  openBrowser: async () => {},
};
