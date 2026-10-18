import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Assessment from "./Assessment";
import Dashboard from "./Dashboard";
import History from "./History";
import Integrations from "./Integrations";
import Overview from "./Overview";
import Plan from "./Plan";

afterEach(() => vi.unstubAllGlobals());

// [screen, body of the empty response, empty-state text]
const SCREENS = [
  ["Overview", Overview, { items: [] }, /No assessment yet/],
  ["Assessment", Assessment, { items: [] }, /No assessment yet/],
  ["Plan", Plan, { items: [] }, /No assessment yet/],
  ["History", History, { items: [] }, /No assessments yet/],
  ["Integrations", Integrations, { items: [] }, /Nothing connected yet/],
  ["Profile", Dashboard, { user_id: "u", profile: null }, /No profile yet/],
] as const;

describe.each(SCREENS)("%s states", (_n, Screen, empty, emptyText) => {
  it("shows a loading status while the request is pending", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise(() => {})),
    );
    render(<Screen />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading");
  });
  it("shows an empty state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json(empty)),
    );
    render(<Screen />);
    expect(await screen.findByText(emptyText)).toBeInTheDocument();
  });
  it("shows an error with retry when the server fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json({ error: { code: "x", message: "Boom", request_id: "r1" } }, { status: 500 }),
      ),
    );
    render(<Screen />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Boom (ref r1)");
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});

it("marks status with text, not colour alone", async () => {
  const { StatusBadge } = await import("../components");
  render(<StatusBadge status="failed" />);
  expect(screen.getByText(/Failed/)).toBeInTheDocument();
});
