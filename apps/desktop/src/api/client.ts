// Single choke point for HTTP. Errors are normalised to ApiError; raw bodies never reach the UI.
export const API_BASE_URL: string = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

export class ApiError extends Error {
  constructor(
    public kind: "network" | "timeout" | "http",
    message: string,
    public status?: number,
    public code?: string,
    public requestId?: string | null,
  ) {
    super(message);
  }
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  token?: string; // explicit override; normally the registered AuthHooks supply it. This client never stores tokens
  anonymous?: boolean; // skip auth entirely (health checks)
  timeoutMs?: number;
  signal?: AbortSignal;
}

async function send<T>(path: string, o: RequestOptions): Promise<T> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort("timeout"), o.timeoutMs ?? 10_000);
  o.signal?.addEventListener("abort", () => ctl.abort());
  try {
    const res = await fetch(`${API_BASE_URL}${path}`, {
      method: o.method ?? "GET",
      headers: {
        ...(o.body !== undefined && { "Content-Type": "application/json" }),
        ...(o.token && { Authorization: `Bearer ${o.token}` }),
      },
      body: o.body === undefined ? undefined : JSON.stringify(o.body),
      signal: ctl.signal,
    });
    if (!res.ok) {
      // /api/v1 envelope: {"error": {code, message, request_id}}
      const e = (await res.json().catch(() => null))?.error;
      const msg = typeof e?.message === "string" ? e.message : `HTTP ${res.status}`;
      throw new ApiError("http", msg, res.status, e?.code, e?.request_id);
    }
    return (res.status === 204 ? undefined : await res.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (ctl.signal.aborted && ctl.signal.reason === "timeout") {
      throw new ApiError("timeout", "The server took too long to respond.");
    }
    throw new ApiError("network", "Cannot reach the server.");
  } finally {
    clearTimeout(timer);
  }
}

// Central auth: every request gets the current token; a 401 refreshes once and replays ONLY idempotent
// methods (a POST that may have run is never silently repeated); otherwise the session is declared lost.
export interface AuthHooks {
  getToken(): Promise<string | null>; // throws ApiError("network") if a needed refresh cannot reach the IdP
  refresh(): Promise<boolean>;
  onSessionLost(): void;
}
let hooks: AuthHooks | null = null;
export const setAuthHooks = (h: AuthHooks | null) => {
  hooks = h;
};
const IDEMPOTENT = new Set(["GET", "HEAD", "PUT", "DELETE"]);

export async function request<T>(path: string, o: RequestOptions = {}): Promise<T> {
  if (!hooks || o.token !== undefined || o.anonymous) return send<T>(path, o);
  const h = hooks;
  try {
    return await send<T>(path, { ...o, token: (await h.getToken()) ?? undefined });
  } catch (e) {
    if (!(e instanceof ApiError) || e.status !== 401) throw e;
    if (IDEMPOTENT.has(o.method ?? "GET") && (await h.refresh())) {
      try {
        return await send<T>(path, { ...o, token: (await h.getToken()) ?? undefined });
      } catch (e2) {
        if (e2 instanceof ApiError && e2.status === 401) h.onSessionLost();
        throw e2;
      }
    }
    h.onSessionLost();
    throw e;
  }
}

export const getHealth = () =>
  request<{ status: string; version: string }>("/health", { timeoutMs: 4000, anonymous: true });
