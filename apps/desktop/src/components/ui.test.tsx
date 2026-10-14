import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import App from "../App";
import { ConnectionProvider, useConnection } from "../connection";
import { ErrorState, Field } from "./ui";

afterEach(() => vi.unstubAllGlobals());

function Probe() {
  const { status } = useConnection();
  return <span>{status}</span>;
}

it("reports offline when the API is down, without crashing", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("down")));
  render(
    <ConnectionProvider>
      <Probe />
    </ConnectionProvider>,
  );
  expect(await screen.findByText("offline")).toBeInTheDocument();
});

it("reports online when health succeeds", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('{"status":"ok","version":"1"}')));
  render(
    <ConnectionProvider>
      <Probe />
    </ConnectionProvider>,
  );
  expect(await screen.findByText("online")).toBeInTheDocument();
});

it("shows the sign-in screen, not app data, when there is no session", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("down")));
  render(
    <MemoryRouter>
      <App />
    </MemoryRouter>,
  );
  expect(await screen.findByRole("button", { name: "Sign in" })).toBeInTheDocument();
  expect(screen.queryByText("Dashboard")).toBeNull();
});

it("labels fields and errors accessibly", () => {
  render(
    <>
      <Field label="Email" error="Required" />
      <ErrorState message="x" />
    </>,
  );
  expect(screen.getByLabelText("Email")).toHaveAccessibleDescription("Required");
});
