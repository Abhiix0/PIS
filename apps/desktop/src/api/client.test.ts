import { afterEach, expect, it, vi } from "vitest";
import { ApiError, request } from "./client";

afterEach(() => vi.unstubAllGlobals());

it("maps the v1 error envelope", async () => {
  const body = JSON.stringify({ error: { code: "forbidden", message: "no", request_id: "r1" } });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(body, { status: 403 })));
  await expect(request("/api/v1/me")).rejects.toMatchObject({
    kind: "http",
    status: 403,
    code: "forbidden",
    requestId: "r1",
  });
});

it("maps network failure without crashing", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fail")));
  await expect(request("/health")).rejects.toBeInstanceOf(ApiError);
  await expect(request("/health")).rejects.toMatchObject({ kind: "network" });
});

it("sends bearer token only when given", async () => {
  const f = vi.fn().mockResolvedValue(new Response("{}"));
  vi.stubGlobal("fetch", f);
  await request("/x", { token: "t" });
  expect(f.mock.calls[0]![1].headers.Authorization).toBe("Bearer t");
});
