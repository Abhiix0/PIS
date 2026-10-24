import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { AppShell } from "../components";
import Dashboard from "./Dashboard";
import Integrations from "./Integrations";
import Overview from "./Overview";

afterEach(() => vi.unstubAllGlobals());

const tokens = Object.values(
  import.meta.glob("../styles/tokens.css", { query: "?raw", import: "default", eager: true }),
).join("") as string;

// WCAG 2.x relative luminance and contrast ratio, on the tokens as written in tokens.css.
const tok = Object.fromEntries(
  [...tokens.matchAll(/--([\w-]+):\s*(#[0-9a-f]{3,6})\s*;/gi)].map((m) => [m[1]!, m[2]!]),
);
const lum = (hex: string) => {
  const h = hex.length === 4 ? [...hex.slice(1)].map((c) => c + c).join("") : hex.slice(1);
  const [r, g, b] = [0, 2, 4].map((i) => {
    const c = parseInt(h.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  }) as [number, number, number];
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const ratio = (a: string, b: string) => {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
};

// [foreground, background, minimum]: pairs actually used in components.css (large text needs 3:1).
const PAIRS: [string, string, number][] = [
  ["text", "bg", 4.5],
  ["muted", "bg", 4.5],
  ["muted", "warn-bg", 4.5],
  ["accent-text", "bg", 4.5],
  ["primary-text", "primary", 4.5],
  ["text", "accent", 4.5],
  ["text-on-dark", "surface-dark", 4.5],
  ["accent", "surface-dark", 3],
  ["ok", "ok-bg", 4.5],
  ["warn", "warn-bg", 4.5],
  ["danger", "danger-bg", 4.5],
  ["info", "info-bg", 4.5],
  ["ok", "bg", 4.5],
  ["danger", "bg", 4.5],
  ["bg", "danger", 4.5],
  ["bg", "info", 4.5],
];
it.each(PAIRS)("contrast %s on %s is at least %s:1", (fg, bg, min) => {
  expect(ratio(tok[fg]!, tok[bg]!)).toBeGreaterThanOrEqual(min);
});

it("the app shell has navigation, header and main landmarks", () => {
  render(
    <MemoryRouter>
      <AppShell title="NexGauge" nav={[{ to: "/a", label: "A" }]}>
        <h1>Page</h1>
      </AppShell>
    </MemoryRouter>,
  );
  expect(screen.getByRole("navigation", { name: "Primary" })).toBeInTheDocument();
  expect(screen.getByRole("main")).toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 1, name: "Page" })).toBeInTheDocument();
});

it("every profile and connect input has an accessible name", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json({ user_id: "u", profile: null, items: [] })),
  );
  const { unmount } = render(<Dashboard />);
  for (const name of ["Name", "Branch", "Graduation year", "CGPA"])
    expect(await screen.findByLabelText(name)).toBeInTheDocument();
  unmount();
  render(<Integrations />);
  await screen.findAllByLabelText("GitHub username");
  for (const box of screen.getAllByRole("textbox")) expect(box).toHaveAccessibleName();
  for (const b of screen.getAllByRole("button")) expect(b).toHaveAccessibleName();
});

const snapshot = {
  id: "a1",
  assessment_type: "rules_assessment",
  readiness_score: null,
  category: null,
  reason: "Per-dimension evidence states.",
  model_version: null,
  created_at: new Date().toISOString(),
  result: {
    assessment_version: "rules-v1",
    evidence_version: "evidence-v2",
    generated_at: new Date().toISOString(),
    stale_after_days: 7,
    dimensions: [
      {
        dimension: "D1",
        title: "GitHub activity consistency",
        evidence_state: "sufficient",
        values: [],
        rule: { id: "d1.activity_trend.v1", text: "t" },
        coverage: "Public GitHub contribution calendar.",
        caveats: ["Counts contributions, not skill."],
      },
    ],
    recommendations: [],
    limitations: "Not a score; says nothing about hiring or placement.",
  },
};

it("Overview states coverage and what the assessment cannot establish", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json({ items: [snapshot] })),
  );
  render(
    <MemoryRouter>
      <Overview />
    </MemoryRouter>,
  );
  const about = await screen.findByRole("region", { name: "About this assessment" });
  expect(about).toHaveTextContent("Public GitHub contribution calendar.");
  expect(about).toHaveTextContent("Cannot establish: Counts contributions, not skill.");
  expect(about).toHaveTextContent("says nothing about hiring or placement");
});

it("the run button is reachable by keyboard and activates with Enter", async () => {
  const f = vi.fn(async (_u: string, init?: RequestInit) =>
    init?.method === "POST" ? Response.json(snapshot, { status: 201 }) : Response.json({ items: [snapshot] }),
  );
  vi.stubGlobal("fetch", f);
  render(
    <MemoryRouter>
      <Overview />
    </MemoryRouter>,
  );
  const run = await screen.findByRole("button", { name: "Run a new assessment" });
  await userEvent.tab();
  expect(run).toHaveFocus();
  await userEvent.keyboard("{Enter}");
  expect(f.mock.calls.some((c) => c[1]?.method === "POST")).toBe(true);
});

it("status and error messages are announced", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("down")));
  render(
    <MemoryRouter>
      <Overview />
    </MemoryRouter>,
  );
  expect(await screen.findByRole("alert")).toBeInTheDocument();
});
