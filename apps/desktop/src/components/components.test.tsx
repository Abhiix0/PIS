import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import {
  AppShell,
  Badge,
  Banner,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Input,
  Loading,
  Select,
  Skeleton,
  Stat,
  Table,
  Tabs,
} from ".";

it("Button defaults to type=button, applies variant, fires onClick", async () => {
  const f = vi.fn();
  render(
    <Button variant="accent" onClick={f}>
      Go
    </Button>,
  );
  const b = screen.getByRole("button", { name: "Go" });
  expect(b).toHaveAttribute("type", "button");
  expect(b).toHaveClass("accent");
  await userEvent.click(b);
  expect(f).toHaveBeenCalledOnce();
});

it("Card, Badge, Banner, Stat, Table render content", () => {
  render(
    <>
      <Card aria-label="c" tone="info">
        x
      </Card>
      <Badge tone="ok">fine</Badge>
      <Banner tone="danger">bad</Banner>
      <Stat label="Projects" value={12} />
      <Table>
        <tbody>
          <tr>
            <td>cell</td>
          </tr>
        </tbody>
      </Table>
    </>,
  );
  expect(screen.getByLabelText("c")).toHaveClass("info");
  expect(screen.getByText("fine")).toHaveClass("ok");
  expect(screen.getByRole("alert")).toHaveTextContent("bad");
  expect(screen.getByText("Projects")).toBeInTheDocument();
  expect(screen.getByRole("cell")).toBeInTheDocument();
});

it("Input and Select link label and error", () => {
  render(
    <>
      <Input label="Email" error="Required" />
      <Select label="Branch" error="Pick one">
        <option>CSE</option>
      </Select>
    </>,
  );
  expect(screen.getByLabelText("Email")).toHaveAccessibleDescription("Required");
  expect(screen.getByLabelText("Branch")).toBeInvalid();
});

function Harness() {
  const [v, setV] = useState("a");
  return (
    <Tabs
      tabs={[
        { id: "a", label: "A" },
        { id: "b", label: "B" },
      ]}
      value={v}
      onChange={setV}
    />
  );
}

it("Tabs move selection with arrow keys", async () => {
  render(<Harness />);
  screen.getByRole("tab", { name: "A" }).focus();
  await userEvent.keyboard("{ArrowRight}");
  expect(screen.getByRole("tab", { name: "B" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("tab", { name: "B" })).toHaveFocus();
});

it("EmptyState, ErrorState (retry), Loading and Skeleton render", async () => {
  const retry = vi.fn();
  render(
    <>
      <EmptyState title="Nothing" hint="Add one" />
      <ErrorState message="boom" onRetry={retry} />
      <Loading label="Wait" />
      <Skeleton />
    </>,
  );
  expect(screen.getByText("Add one")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(retry).toHaveBeenCalled();
  expect(screen.getByText("boom").closest("[role=alert]")).not.toBeNull();
  expect(screen.getByRole("status")).toHaveTextContent("Wait");
});

it("AppShell shows nav, marks the current page, renders children", () => {
  render(
    <MemoryRouter initialEntries={["/b"]}>
      <AppShell
        title="PIS"
        nav={[
          { to: "/a", label: "A" },
          { to: "/b", label: "B" },
        ]}
        status={<span>ok</span>}
      >
        <p>body</p>
      </AppShell>
    </MemoryRouter>,
  );
  expect(screen.getByRole("navigation", { name: "Primary" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "B" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByText("body")).toBeInTheDocument();
});
