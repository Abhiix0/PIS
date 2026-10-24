import { expect, it } from "vitest";
import { buildCsp, origin } from "../../scripts/csp.mjs";
import conf from "../../src-tauri/tauri.conf.json";

const env = {
  VITE_API_BASE_URL: "https://api.example.com/",
  VITE_AUTH_ISSUER: "https://idp.example.com/tenant",
};

it("release CSP allows exactly the API and IdP origins, never a blanket https:", () => {
  const csp = buildCsp(env);
  const connect = /connect-src ([^;]+);/.exec(csp)![1]!.split(" ");
  expect(connect).toEqual([
    "'self'",
    "ipc:",
    "http://ipc.localhost",
    "https://api.example.com",
    "https://idp.example.com",
  ]);
  expect(csp).not.toMatch(/(^|[ ;])https:([ ;]|$)/);
  expect(csp).not.toContain("localhost:8000");
});

it("rejects plain http for remote hosts and invalid URLs", () => {
  expect(() => origin("http://api.example.com", "X")).toThrow(/https/);
  expect(() => origin("not a url", "X")).toThrow(/valid URL/);
  expect(origin("http://localhost:8000", "X")).toBe("http://localhost:8000");
  expect(() => buildCsp({ ...env, CSP_EXTRA_ORIGINS: "http://evil.example" })).toThrow();
});

it("the committed base config no longer allows arbitrary https", () => {
  const csp = conf.app.security.csp;
  expect(csp).not.toMatch(/(^|[ ;])https:([ ;]|$)/);
  expect(csp).toContain("http://localhost:8000");
});
