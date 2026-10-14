import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import App from "../App";
import { ErrorState, Field } from "./ui";

afterEach(() => vi.unstubAllGlobals());

it("shows loading then offline state when the API is down, without crashing", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("down")));
  render(
    <MemoryRouter>
      <App />
    </MemoryRouter>,
  );
  expect(screen.getAllByRole("status").length).toBeGreaterThan(0);
  expect(await screen.findByRole("alert")).toHaveTextContent(/cannot reach/i);
});

it("shows online when health succeeds", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('{"status":"ok","version":"1"}')));
  render(
    <MemoryRouter>
      <App />
    </MemoryRouter>,
  );
  expect(await screen.findByText("API online")).toBeInTheDocument();
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
