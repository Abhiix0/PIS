import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import Dashboard, { validate } from "./Dashboard";

afterEach(() => vi.unstubAllGlobals());
const json = (b: unknown, status = 200) => Response.json(b, { status });
const err = (status: number, code: string, message: string) =>
  json({ error: { code, message, request_id: "r9" } }, status);

function serve(me: unknown, put?: () => Response) {
  const f = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "PUT") return put!();
    return url.endsWith("/me") ? json(me) : json({ items: [] });
  });
  vi.stubGlobal("fetch", f);
  return f;
}

it("validates against the server's limits", () => {
  expect(validate({ display_name: "", graduation_year: "1999", cgpa: "11" })).toEqual({
    display_name: expect.any(String),
    graduation_year: expect.any(String),
    cgpa: expect.any(String),
  });
  expect(validate({ display_name: "A", graduation_year: "", cgpa: "" })).toEqual({});
});

it("shows an empty state, saves a new profile, and shows it", async () => {
  const p = { id: "1", display_name: "Ada", branch: null, graduation_year: null, cgpa: 8.5 };
  const f = serve({ user_id: "u", profile: null }, () => json(p, 201));
  render(<Dashboard />);
  expect(await screen.findByText(/No profile yet/)).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Name"), "Ada");
  await userEvent.type(screen.getByLabelText("CGPA"), "8.5");
  await userEvent.click(screen.getByText("Save profile"));
  expect(await screen.findByText("Ada")).toBeInTheDocument();
  const put = f.mock.calls.find((c) => c[1]?.method === "PUT")!;
  expect(JSON.parse(put[1]!.body as string)).toEqual({
    display_name: "Ada",
    branch: null,
    graduation_year: null,
    cgpa: 8.5,
  });
});

it("blocks invalid input client-side without calling the API", async () => {
  const f = serve({ user_id: "u", profile: null });
  render(<Dashboard />);
  await userEvent.click(await screen.findByText("Save profile"));
  expect(screen.getByText(/Enter a name/)).toBeInTheDocument();
  expect(f.mock.calls.every((c) => c[1]?.method !== "PUT")).toBe(true);
});

it("keeps the input and shows the server's message on a failed save", async () => {
  serve({ user_id: "u", profile: null }, () => err(409, "conflict", "Profile changed elsewhere"));
  render(<Dashboard />);
  await userEvent.type(await screen.findByLabelText("Name"), "Ada");
  await userEvent.click(screen.getByText("Save profile"));
  await waitFor(() =>
    expect(screen.getByRole("alert")).toHaveTextContent("Profile changed elsewhere (ref r9)"),
  );
  expect(screen.getByLabelText("Name")).toHaveValue("Ada");
});

it("offers retry when the backend is unreachable", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("down")));
  render(<Dashboard />);
  expect(await screen.findByRole("alert")).toHaveTextContent(/cannot reach the server/i);
  expect(screen.getByText("Retry")).toBeInTheDocument();
});
