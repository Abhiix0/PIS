# Desktop sign-in and profile slice

Flow: Sign in -> system browser (OIDC authorization code + PKCE, S256) -> loopback redirect `http://127.0.0.1:<random port>/callback`
(RFC 8252; Rust `auth_listen`/`auth_wait`) -> token exchange from the webview -> `GET /api/v1/me`, `GET /api/v1/integrations`.
Only `VITE_AUTH_ISSUER` and `VITE_AUTH_CLIENT_ID`; endpoints come from RFC 8414 metadata at
`/.well-known/oauth-authorization-server`, whose `issuer` must equal `VITE_AUTH_ISSUER`. No `audience` parameter is sent.
Clerk setup: Public OAuth app, Require PKCE, scopes `openid email offline_access`, redirect `http://127.0.0.1/callback`
(the runtime request sends `http://127.0.0.1:<port>/callback`; confirm with a real sign-in). Dev builds log the access-token claim
names, `iss`, `aud`, `azp`, `client_id` (never the token) to the webview console as `[auth-diagnostic]`.

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

## Upgrade behavior (Phase 9.1)
The app identifier (`app.pis.desktop`) and the credential-store service name (`SERVICE` in `src-tauri/src`, also `app.pis.desktop`, account `refresh-token`) are unchanged since the first installer (git history), so an existing sign-in should survive an upgrade. **Unverified:** no upgrade was run; how the NSIS installer behaves over an existing install is untested.
