// Dev-only fetch stub (VITE_MOCK_API=1). Imported dynamically behind import.meta.env.DEV, so prod bundles drop it.
// URL flags: #signed-out (sign-in screen), ?mock=empty|error|slow (state sets).
import type { Native } from "../auth/native";
import { API_BASE_URL } from "./client";

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
const A = (id: string, d: number) => ({
  id,
  assessment_type: "insufficient_evidence",
  readiness_score: null,
  category: null,
  reason: "Real accounts do not receive a model score yet; this snapshot summarises your evidence.",
  model_version: null,
  created_at: ago(d),
});
const assessments = [A("a3", 1), A("a2", 9), A("a1", 20)];
const evidence = (repos: number, solved: number) => ({
  evidence_version: "evidence-v1",
  cgpa: { value: 8.4, provenance: "user_entered" },
  github: {
    sync_run_id: "11111111-aaaa",
    synced_at: ago(2),
    provenance: "observed",
    values: {
      github_public_repo_count: repos,
      commits_in_sampled_repos: repos * 11,
      repos_sampled: Math.min(repos, 10),
    },
  },
  leetcode: {
    sync_run_id: "22222222-bbbb",
    synced_at: ago(12),
    provenance: "observed",
    values: {
      leetcode_solved_all: solved,
      leetcode_solved_easy: solved * 0.5,
      leetcode_solved_medium: solved * 0.4,
      leetcode_solved_hard: solved * 0.1,
    },
  },
});
const ev: Record<string, unknown> = { a3: evidence(14, 120), a2: evidence(11, 90), a1: evidence(8, 60) };
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
    const m = /assessments\/(\w+)\/evidence/.exec(path);
    if (m) return json({ assessment_id: m[1], evidence: ev[m[1]!] });
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
      return u.pathname.endsWith("openid-configuration")
        ? json({ authorization_endpoint: "http://mock.idp/auth", token_endpoint: "http://mock.idp/token" })
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
