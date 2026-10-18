// Generic OIDC (authorization code + PKCE, public client). Endpoints come from discovery; nothing here is provider specific.
export class AuthError extends Error {
  constructor(
    public kind: "network" | "invalid_grant" | "cancelled" | "state" | "config" | "other",
    message: string,
  ) {
    super(message);
  }
}

export interface Tokens {
  access: string;
  expiresAt: number; // epoch ms
  refresh?: string;
}
export interface Meta {
  authorization_endpoint: string;
  token_endpoint: string;
  revocation_endpoint?: string;
}

export const config = () => ({
  issuer: (import.meta.env.VITE_AUTH_ISSUER ?? "").replace(/\/$/, ""),
  clientId: import.meta.env.VITE_AUTH_CLIENT_ID ?? "",
  audience: import.meta.env.VITE_AUTH_AUDIENCE as string | undefined,
});

const b64url = (b: Uint8Array) =>
  btoa(String.fromCharCode(...b))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
const rand = () => b64url(crypto.getRandomValues(new Uint8Array(32)));

export async function makePkce() {
  const verifier = rand();
  const hash = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  return { verifier, challenge: b64url(new Uint8Array(hash)), state: rand() };
}

export async function discover(issuer: string): Promise<Meta> {
  if (!issuer || !config().clientId) throw new AuthError("config", "Sign-in is not configured.");
  try {
    const m = await (await fetch(`${issuer}/.well-known/openid-configuration`)).json();
    if (!m.authorization_endpoint || !m.token_endpoint) throw new Error("incomplete");
    return m;
  } catch {
    throw new AuthError("network", "Cannot reach the sign-in service.");
  }
}

export function buildAuthUrl(m: Meta, redirectUri: string, p: { challenge: string; state: string }) {
  const { clientId, audience } = config();
  const q = new URLSearchParams({
    response_type: "code",
    client_id: clientId,
    redirect_uri: redirectUri,
    scope: "openid offline_access",
    code_challenge: p.challenge,
    code_challenge_method: "S256",
    state: p.state,
  });
  if (audience) q.set("audience", audience);
  return `${m.authorization_endpoint}?${q}`;
}

/** `query` is the raw query string of the loopback redirect. Returns the code or throws. */
export function parseCallback(query: string, state: string): string {
  const q = new URLSearchParams(query);
  if (q.get("state") !== state) throw new AuthError("state", "Sign-in response did not match this request.");
  if (q.get("error"))
    throw new AuthError(
      q.get("error") === "access_denied" ? "cancelled" : "other",
      "Sign-in was not completed.",
    );
  const code = q.get("code");
  if (!code) throw new AuthError("other", "Sign-in was not completed.");
  return code;
}

async function post(endpoint: string, form: Record<string, string>) {
  let res: Response;
  try {
    res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ client_id: config().clientId, ...form }),
    });
  } catch {
    throw new AuthError("network", "Cannot reach the sign-in service.");
  }
  return res;
}

async function toTokens(res: Response, prevRefresh?: string): Promise<Tokens> {
  const j = await res.json().catch(() => null);
  if (!res.ok || !j?.access_token) {
    // Only an explicit invalid_grant means the session is really over; anything else may be transient.
    throw j?.error === "invalid_grant"
      ? new AuthError("invalid_grant", "Your session has ended.")
      : new AuthError(res.status >= 500 ? "network" : "other", "Sign-in service rejected the request.");
  }
  return {
    access: j.access_token,
    expiresAt: Date.now() + (j.expires_in ?? 300) * 1000,
    refresh: j.refresh_token ?? prevRefresh,
  };
}

export async function exchangeCode(m: Meta, code: string, verifier: string, redirectUri: string) {
  return toTokens(
    await post(m.token_endpoint, {
      grant_type: "authorization_code",
      code,
      code_verifier: verifier,
      redirect_uri: redirectUri,
    }),
  );
}
export async function refreshTokens(m: Meta, refresh: string) {
  return toTokens(
    await post(m.token_endpoint, { grant_type: "refresh_token", refresh_token: refresh }),
    refresh,
  );
}
export async function revoke(m: Meta, refresh: string) {
  if (m.revocation_endpoint)
    await post(m.revocation_endpoint, { token: refresh, token_type_hint: "refresh_token" }).catch(() => {});
}
