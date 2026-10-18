# Desktop sign-in and profile slice

Flow: Sign in -> system browser (OIDC authorization code + PKCE, S256) -> loopback redirect `http://127.0.0.1:<random port>/callback`
(RFC 8252; Rust `auth_listen`/`auth_wait`) -> token exchange from the webview -> `GET /api/v1/me`, `GET /api/v1/integrations`.
Provider-agnostic: only `VITE_AUTH_ISSUER`, `VITE_AUTH_CLIENT_ID` (+ optional `VITE_AUTH_AUDIENCE`); endpoints come from
`/.well-known/openid-configuration`. The IdP must allow a loopback redirect on any port and `offline_access` (refresh token).

Where things live
- Access token: JS memory only. Refresh token: Windows Credential Manager (`keyring`, Rust commands `token_*`); never localStorage, never logged.
- `src/auth/oidc.ts` protocol, `src/auth/session.tsx` state machine, `src/api/client.ts` central 401 handling, `src/screens/Dashboard.tsx`.

Rules enforced centrally (`client.ts`)
- Every request carries the current token (refresh if <30 s left, single-flight).
- 401 -> refresh once and replay **only GET/HEAD/PUT/DELETE**. POST is never replayed; the session is declared lost.
- Refresh `invalid_grant` -> credential cleared, "session expired". IdP/network failure -> stored token kept, retry offered.
- Sign out: `POST /auth/logout` (revokes older tokens server-side), IdP revocation if advertised, then local clear.

Limits / open
- Rust (`src-tauri`) is compiled only by CI (`desktop.yml`); no local toolchain was available when written.
- CSP `connect-src` allows `https:` and `localhost:8000`; an http IdP on another local port needs a CSP edit for dev.
- Concrete IdP not chosen (PRD §19); logout does not do IdP end-session (browser SSO cookie may remain).
- No in-app test against a real IdP has been run.
