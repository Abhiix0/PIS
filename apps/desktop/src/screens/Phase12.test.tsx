import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { FEATURE_DEFS } from "../lib/assessment";
import Integrations, { describeRun } from "./Integrations";
import Overview from "./Overview";

afterEach(() => vi.unstubAllGlobals());
const json = (b: unknown, status = 200) => Response.json(b, { status });
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

it("overview offers retry when the backend is down", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("down")));
  render(
    <MemoryRouter>
      <Overview />
    </MemoryRouter>,
  );
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
