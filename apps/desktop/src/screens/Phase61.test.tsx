import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Assessment, Dimension, EvidenceState } from "../api/v1";
import { DEMO } from "../lib/assessment";
import AssessmentScreen from "./Assessment";
import History from "./History";
import Overview from "./Overview";
import Plan from "./Plan";

afterEach(() => vi.unstubAllGlobals());
const json = (b: unknown, status = 200) => Response.json(b, { status });
const ago = (d: number) => new Date(Date.now() - d * 864e5).toISOString();

const value = (name: string, v: number | string | null, state = "present") => ({
  name,
  value: v,
  provenance: "observed",
  value_state: state,
  event_at_precision: "repo_push",
  collected_at: ago(2),
  synced_at: ago(2),
  sync_run_id: "abcdef12-0000",
});
const dim = (
  id: string,
  state: EvidenceState,
  values = [value("github_public_repo_count", 3)],
): Dimension => ({
  dimension: id,
  title: `Title ${id}`,
  evidence_state: state,
  values: state === "no_evidence" ? [] : values,
  rule: { id: `${id.toLowerCase()}.rule.v1`, text: `Rule text ${id}` },
  coverage: `Coverage ${id}`,
  caveats: [`Caveat ${id}`],
  ...(state === "source_failed" ? { last_sync: { status: "failed", error_code: "rate_limited" } } : {}),
});
const assessment = (states: EvidenceState[], extra: Partial<Assessment> = {}): Assessment => ({
  id: "a1",
  assessment_type: states.every((s) => s === "no_evidence") ? "insufficient_evidence" : "rules_assessment",
  readiness_score: null,
  category: null,
  reason: "Per-dimension evidence states.",
  model_version: null,
  created_at: ago(1),
  result: {
    assessment_version: "rules-v1",
    evidence_version: "evidence-v2",
    generated_at: ago(1),
    stale_after_days: 7,
    dimensions: states.map((s, i) => dim(`D${i + 1}`, s)),
    recommendations: [
      {
        id: "rec-1-r4",
        rule_id: "r4.stale",
        priority: 1,
        dimension: "D1",
        action: "Re-sync to refresh this data.",
        reason: "The last import is old.",
        evidence_refs: [{ dimension: "D1", name: null, sync_run_id: "abcdef12-0000" }],
        limitation: "Based only on public activity.",
      },
    ],
    limitations: "Not a score; says nothing about hiring or placement.",
  },
  ...extra,
});
const serve = (a: Assessment | null) =>
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => json({ items: a ? [a] : [] })),
  );
const inRouter = (ui: React.ReactElement) => render(<MemoryRouter>{ui}</MemoryRouter>);

describe.each([
  ["sufficient", ["sufficient", "sufficient"], /Sufficient/],
  ["partial", ["partial", "sufficient"], /Partial/],
  ["stale", ["stale", "sufficient"], /Stale/],
  ["source_failed", ["source_failed", "sufficient"], /Sync failed/],
  ["no_evidence", ["no_evidence", "no_evidence"], /No evidence/],
] as const)("state matrix: %s", (_n, states, label) => {
  it("Assessment shows every dimension with its state, rule, coverage and caveats", async () => {
    serve(assessment([...states]));
    inRouter(<AssessmentScreen />);
    const card = await screen.findByRole("heading", { name: "Title D1" });
    expect(card).toBeInTheDocument();
    expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    expect(screen.getByText(/Rule d1.rule.v1:/)).toBeInTheDocument();
    expect(screen.getByText(/Coverage D1/)).toBeInTheDocument();
    expect(screen.getByText("Caveat D1")).toBeInTheDocument();
    expect(screen.getByText(/Not a score/)).toBeInTheDocument();
  });
  it("Overview never shows a score and warns on stale or failed data", async () => {
    serve(assessment([...states]));
    inRouter(<Overview />);
    expect(await screen.findByText("Not scored")).toBeInTheDocument();
    const warns = states.some((s) => s === "stale" || s === "source_failed");
    expect(!!screen.queryByText(/stale or its last sync failed/)).toBe(warns);
  });
});

it("a failed sync keeps the last-known-good values visible and says so", async () => {
  serve(assessment(["source_failed"]));
  inRouter(<AssessmentScreen />);
  expect(await screen.findByText(/Last sync failed \(rate_limited\)/)).toBeInTheDocument();
  expect(screen.getByText("github_public_repo_count")).toBeInTheDocument();
});

it("a measured zero reads as a reported zero, a missing value as not available", async () => {
  const a = assessment(["sufficient"]);
  a.result!.dimensions[0]!.values = [
    value("github_public_repo_count", 0, "measured_zero"),
    value("trend_direction", null, "not_collected"),
  ];
  serve(a);
  inRouter(<AssessmentScreen />);
  expect(await screen.findByText("0 (reported by the provider)")).toBeInTheDocument();
  expect(screen.getByText("Not available")).toBeInTheDocument();
});

it("a snapshot from before rules-v1 is flagged, not rendered as an empty assessment", async () => {
  serve(assessment(["sufficient"], { result: null, assessment_type: "insufficient_evidence" }));
  inRouter(<AssessmentScreen />);
  expect(await screen.findByText(/before the current assessment rules/)).toBeInTheDocument();
});

it("Plan renders server recommendations with their rule id and evidence, nothing client-made", async () => {
  serve(assessment(["stale"]));
  inRouter(<Plan />);
  expect(await screen.findByText(/Re-sync to refresh this data/)).toBeInTheDocument();
  expect(screen.getByText(/Rule r4.stale/)).toHaveTextContent("D1 (run abcdef12)");
  const empty = assessment(["sufficient"]);
  empty.result!.recommendations = [];
  serve(empty);
  inRouter(<Plan />);
  expect(await screen.findByText(/No priorities from current evidence/)).toBeInTheDocument();
});

it("offline: an unreachable API shows an error, never old data as current", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("down")));
  inRouter(<Plan />);
  expect(await screen.findByRole("alert")).toHaveTextContent(/cannot reach the server/i);
  expect(screen.queryByText(/Re-sync/)).toBeNull();
});

describe("first run", () => {
  const serveSteps = (profile: unknown, items: unknown[]) =>
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        url.includes("/assessments")
          ? json({ items: [] })
          : url.endsWith("/me")
            ? json({ user_id: "u", profile })
            : json({ items }),
      ),
    );
  const prof = { id: "p", display_name: "A", branch: null, graduation_year: null, cgpa: null };

  it("points to the profile step first and resumes from server state", async () => {
    serveSteps(null, []);
    inRouter(<Overview />);
    const step = (await screen.findByText(/Create your profile/)).closest("li")!;
    expect(within(step).getByText("Next")).toBeInTheDocument();
    expect(within(step).getByRole("link", { name: "Open Profile" })).toHaveAttribute("href", "/dashboard");
    expect(screen.queryByRole("button", { name: "Run assessment" })).toBeNull();
  });

  it("moves on to connect, then sync, then offers the first assessment", async () => {
    serveSteps(prof, []);
    const { unmount } = render(
      <MemoryRouter>
        <Overview />
      </MemoryRouter>,
    );
    expect((await screen.findByText(/Connect your GitHub username/)).closest("li")).toHaveTextContent("Next");
    unmount();
    serveSteps(prof, [{ id: "i", provider: "github", last_success_at: null }]);
    const second = render(
      <MemoryRouter>
        <Overview />
      </MemoryRouter>,
    );
    expect((await screen.findByText(/Run your first sync/)).closest("li")).toHaveTextContent("Next");
    second.unmount();
    serveSteps(prof, [{ id: "i", provider: "github", last_success_at: ago(0) }]);
    inRouter(<Overview />);
    expect(await screen.findByRole("button", { name: "Run assessment" })).toBeInTheDocument();
  });
});

it("History compares through the server and shows its disclosures", async () => {
  const items = [
    assessment(["sufficient"], { id: "x", created_at: ago(5) }),
    assessment(["stale"], { id: "y" }),
  ];
  const f = vi.fn(async (url: string) =>
    url.includes("/compare/")
      ? json({
          from: { id: "x", created_at: ago(5) },
          to: { id: "y", created_at: ago(1) },
          comparable: true,
          disclosures: ["D1 evidence state changed: sufficient to stale."],
          dimensions: [
            {
              dimension: "D1",
              from_state: "sufficient",
              to_state: "stale",
              deltas: [{ name: "github_public_repo_count", from: 3, to: 5, delta: 2 }],
            },
          ],
        })
      : json({ items }),
  );
  vi.stubGlobal("fetch", f);
  inRouter(<History />);
  const boxes = await screen.findAllByRole("checkbox");
  await userEvent.click(boxes[0]!);
  await userEvent.click(boxes[1]!);
  await userEvent.click(screen.getByRole("button", { name: /Compare selected/ }));
  expect(await screen.findByText(/evidence state changed/)).toBeInTheDocument();
  expect(f.mock.calls.some((c) => /assessments\/x\/compare\/y$/.test(c[0] as string))).toBe(true);
  expect(screen.getByText("2")).toBeInTheDocument();
});

it("History says snapshots are not comparable when the server says so", async () => {
  const items = [
    assessment(["sufficient"], { id: "x", created_at: ago(5) }),
    assessment(["sufficient"], { id: "y" }),
  ];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) =>
      url.includes("/compare/")
        ? json({
            from: { id: "x", created_at: ago(5) },
            to: { id: "y", created_at: ago(1) },
            comparable: false,
            disclosures: ["Versions differ: values are not differenced."],
            dimensions: [],
          })
        : json({ items }),
    ),
  );
  inRouter(<History />);
  const boxes = await screen.findAllByRole("checkbox");
  await userEvent.click(boxes[0]!);
  await userEvent.click(boxes[1]!);
  await userEvent.click(screen.getByRole("button", { name: /Compare selected/ }));
  expect(await screen.findByRole("alert")).toHaveTextContent(/cannot be compared/);
  expect(screen.getByText(/not differenced/)).toBeInTheDocument();
});

describe("no demo data outside demo mode", () => {
  it("DEMO is off in tests (no VITE_MOCK_API)", () => {
    expect(DEMO).toBe(false);
  });
  // Built by `npm run build`; the check is skipped when there is no dist/ yet.
  const bundles = Object.values(
    import.meta.glob("../../dist/assets/*.js", { query: "?raw", import: "default", eager: true }),
  ) as string[];
  it.skipIf(bundles.length === 0)("the production bundle contains no mock module or sample data", () => {
    const js = bundles.join(" ");
    expect(js).not.toContain("ada-codes");
    expect(js).not.toContain("Sample data only");
    expect(js).not.toContain("mock.idp");
  });
});
