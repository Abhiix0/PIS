import { afterEach, expect, it, vi } from "vitest";
import { ApiError, request, setAuthHooks } from "./client";

afterEach(() => {
  setAuthHooks(null);
  vi.unstubAllGlobals();
});
const res = (s: number) => new Response(s === 204 ? null : "{}", { status: s });
function hooks(over = {}) {
  const h = {
    getToken: vi.fn().mockResolvedValue("t"),
    refresh: vi.fn().mockResolvedValue(true),
    onSessionLost: vi.fn(),
    ...over,
  };
  setAuthHooks(h);
  return h;
}

it("attaches the token and skips auth for anonymous calls", async () => {
  const f = vi.fn().mockImplementation(() => Promise.resolve(res(200)));
  vi.stubGlobal("fetch", f);
  hooks();
  await request("/x");
  await request("/health", { anonymous: true });
  expect(f.mock.calls[0]![1].headers.Authorization).toBe("Bearer t");
  expect(f.mock.calls[1]![1].headers.Authorization).toBeUndefined();
});

it("on 401 refreshes once and replays an idempotent request", async () => {
  const f = vi.fn().mockResolvedValueOnce(res(401)).mockResolvedValueOnce(res(200));
  vi.stubGlobal("fetch", f);
  const h = hooks();
  await request("/x", { method: "PUT", body: {} });
  expect(f).toHaveBeenCalledTimes(2);
  expect(h.refresh).toHaveBeenCalledOnce();
  expect(h.onSessionLost).not.toHaveBeenCalled();
});

it("never replays a POST after 401; the session is declared lost", async () => {
  const f = vi.fn().mockResolvedValue(res(401));
  vi.stubGlobal("fetch", f);
  const h = hooks();
  await expect(request("/x", { method: "POST" })).rejects.toMatchObject({ status: 401 });
  expect(f).toHaveBeenCalledTimes(1);
  expect(h.refresh).not.toHaveBeenCalled();
  expect(h.onSessionLost).toHaveBeenCalledOnce();
});

it("declares the session lost when the replay is still 401, and ignores 403", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(res(401)));
  const h = hooks();
  await expect(request("/x")).rejects.toBeInstanceOf(ApiError);
  expect(h.onSessionLost).toHaveBeenCalledOnce();
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(res(403)));
  const h2 = hooks();
  await expect(request("/x")).rejects.toMatchObject({ status: 403 });
  expect(h2.onSessionLost).not.toHaveBeenCalled();
});
