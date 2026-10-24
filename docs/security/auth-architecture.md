# Auth and session architecture

**Decision (user-approved):** managed OIDC identity provider; the API only *verifies* tokens. Provider (Auth0/Clerk/Supabase/Keycloak…) is configuration, not code: `AUTH_ISSUER`, `AUTH_AUDIENCE`, `AUTH_JWKS_URL`. No passwords, signup, email verification or recovery live in PIS; those are the IdP's. PRD §19 #2 is resolved to "managed IdP"; the concrete provider is still open.

**Desktop (public client):** must use authorization-code + PKCE against the IdP, hold no client secret, and keep the refresh token in OS secure storage (desktop session work). The API never issues or sees refresh tokens. No desktop bundle exists yet, so "no secret in the bundle" is not yet testable.

**Verification (`app/auth.py`):** RS256 only (`alg=none`/HS* rejected), signature via JWKS, `iss`, `aud`, `exp`, `iat`, `sub` required. Unconfigured auth fails closed (401). Failures return one generic 401; 20 bad attempts/min/IP then 429.

**Identity → data:** first valid token creates a `users` row keyed by `sub` (migration 004). `profiles.user_id` is the ownership key; handlers filter `WHERE id = :id AND user_id = :caller`, so another user's profile is a 404, identical to a missing one.

**Roles:** operator = verified token whose `AUTH_ROLE_CLAIM` list (default `pis_roles`) contains `pis_operator`. The `X-Admin-Key` mechanism is removed. Legacy `students`-keyed routes (`/students`, `/ingest`, `/pipeline`, `/predict`, `/prediction`, `/features`, `/insights`, `/ranking`) and `/admin` are operator-only: they hold demo/seed data with no owner and are never assigned to a user (ADR-0001). `/health*` stays public.

**Sessions/revocation:** access tokens are short-lived (IdP-configured). `POST /auth/logout` sets `users.sessions_valid_after`; tokens with earlier `iat` get 401. `users.status != active` → 403. Revoking at the IdP is still required to stop refresh.

**Abuse limits:** in-process sliding-window limiter (10/min per subject on pipeline/ingest/predict/admin); 64 KiB body cap (Content-Length based); batch ≤ 20, ranking limit ≤ 100. Logs record method/path/status only, never headers or tokens.

**Known gaps:** limiter is per-process; chunked bodies bypass the size check; background-worker identity/scopes are not implemented (no worker exists); legacy students are not backfilled to `profiles`; `ADMIN_KEY` references remain in historical reports.

## IdP evaluation (decision 8, 2026-10-24): vendor still OPEN
Required of the IdP: authorization code + PKCE for a public native client, a loopback redirect on any port, `offline_access` refresh tokens, RS256 JWTs with `iss`/`aud`, and a custom role claim (`pis_roles`) in the token the API receives. Desktop-side behaviour is in `docs/security/desktop-session.md`.

Clerk, from vendor documentation read on 2026-10-24 (nothing configured or run): it can add custom claims to its session token (4 KB token limit) and added a PKCE option in Nov 2025, but that option is for Clerk acting as a *client* of another OAuth provider. Clerk's own guide says the token it returns when Clerk acts as an OAuth/OIDC IdP is not a Clerk session JWT. Loopback redirects on arbitrary ports, `offline_access`, and the audience/claims of the token Clerk-as-IdP issues were **not** found in the documentation. **Verdict: unverified; Clerk is not shown to meet the requirements.** Phase 3.2 must test it live with a dev tenant, or fall back to another OIDC provider (to be evaluated the same way; none is verified). Free-plan limits were not checked.
