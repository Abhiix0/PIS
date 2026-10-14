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
  token?: string; // supplied by the (future) auth layer; this client never stores tokens
  timeoutMs?: number;
  signal?: AbortSignal;
}

export async function request<T>(path: string, o: RequestOptions = {}): Promise<T> {
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

export const getHealth = () => request<{ status: string; version: string }>("/health", { timeoutMs: 4000 });
