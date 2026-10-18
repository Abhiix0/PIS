import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { SessionProvider, useSession } from "./session";
import { parseCallback, makePkce } from "./oidc";
import { setAuthHooks } from "../api/client";
import type { Native } from "./native";

const META = {
  authorization_endpoint: "https://idp/auth",
  token_endpoint: "https://idp/token",
  revocation_endpoint: "https://idp/revoke",
};
let calls: string[];
function idp(token: (form: URLSearchParams) => Response | Promise<Response>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push(url);
      if (url.endsWith("openid-configuration")) return Response.json(META);
      if (url === META.token_endpoint) return token(init!.body as URLSearchParams);
      return new Response(null, { status: 204 }); // revoke + /auth/logout
    }),
  );
}
const ok = (rt = "rt2") => Response.json({ access_token: "at", refresh_token: rt, expires_in: 300 });
const bad = (error: string, status = 400) => Response.json({ error }, { status });

function fakeNative(
  stored: string | null,
  cb?: (state: string) => string,
): Native & { saved: string[]; store: { v: string | null } } {
  const store = { v: stored };
  const saved: string[] = [];
  let url = "";
  return {
    store,
    saved,
    loadRefresh: async () => store.v,
    saveRefresh: async (t: string) => void ((store.v = t), saved.push(t)),
    clearRefresh: async () => void (store.v = null),
    listen: async () => 4242,
    openBrowser: async (u: string) => void (url = u),
    waitCallback: async () => cb!(new URL(url).searchParams.get("state")!),
  } as never;
}

function Probe() {
  const s = useSession();
  return (
    <div>
      <span data-testid="s">{s.state}</span>
      <span data-testid="n">{s.notice}</span>
      <button onClick={() => void s.signIn()}>in</button>
      <button onClick={() => void s.signOut()}>out</button>
    </div>
  );
}
const mount = (n: Native) =>
  render(
    <SessionProvider native={n}>
      <Probe />
    </SessionProvider>,
  );

beforeEach(() => {
  calls = [];
  vi.stubEnv("VITE_AUTH_ISSUER", "https://idp");
  vi.stubEnv("VITE_AUTH_CLIENT_ID", "cid");
});
afterEach(() => {
  setAuthHooks(null);
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

it("signs in with PKCE and stores only the refresh token natively", async () => {
  let form!: URLSearchParams;
  idp((f) => ((form = f), ok()));
  const n = fakeNative(null, (state) => `code=abc&state=${state}`);
  mount(n);
  await waitFor(() => expect(screen.getByTestId("s")).toHaveTextContent("signed-out"));
  await userEvent.click(screen.getByText("in"));
  await waitFor(() => expect(screen.getByTestId("s")).toHaveTextContent("signed-in"));
  expect(form.get("grant_type")).toBe("authorization_code");
  expect(form.get("code_verifier")).toBeTruthy();
  expect(form.get("redirect_uri")).toBe("http://127.0.0.1:4242/callback");
  expect(n.saved).toEqual(["rt2"]);
});

it("treats a denied sign-in as cancellation, not an error", async () => {
  idp(() => ok());
  mount(fakeNative(null, (state) => `error=access_denied&state=${state}`));
  await waitFor(() => expect(screen.getByTestId("s")).toHaveTextContent("signed-out"));
  await userEvent.click(screen.getByText("in"));
  await waitFor(() => expect(screen.getByTestId("n")).toHaveTextContent("Sign-in cancelled."));
});

it("restores a session from the stored refresh token", async () => {
  idp(() => ok("rotated"));
  const n = fakeNative("old");
  mount(n);
  await waitFor(() => expect(screen.getByTestId("s")).toHaveTextContent("signed-in"));
  expect(n.saved).toEqual(["rotated"]);
});

it("an invalid_grant on restore clears the store and says the session expired", async () => {
  idp(() => bad("invalid_grant"));
  const n = fakeNative("old");
  mount(n);
  await waitFor(() => expect(screen.getByTestId("n")).toHaveTextContent("expired"));
  expect(n.store.v).toBeNull();
});

it("an unreachable IdP on restore keeps the stored token so the user can retry", async () => {
  idp(() => bad("server_error", 503));
  const n = fakeNative("old");
  mount(n);
  await waitFor(() => expect(screen.getByTestId("n")).toHaveTextContent("Cannot reach"));
  expect(n.store.v).toBe("old");
});

it("sign out revokes server-side and at the IdP, then clears the credential", async () => {
  idp(() => ok());
  const n = fakeNative("old");
  mount(n);
  await waitFor(() => expect(screen.getByTestId("s")).toHaveTextContent("signed-in"));
  await act(() => userEvent.click(screen.getByText("out")));
  await waitFor(() => expect(screen.getByTestId("s")).toHaveTextContent("signed-out"));
  expect(calls.some((u) => u.endsWith("/auth/logout"))).toBe(true);
  expect(calls).toContain(META.revocation_endpoint);
  expect(n.store.v).toBeNull();
});

it("rejects a callback whose state does not match", async () => {
  expect(() => parseCallback("code=a&state=evil", "good")).toThrow();
  const p = await makePkce();
  expect(p.challenge).not.toBe(p.verifier);
});
