# Desktop shell

Location: `apps/desktop/` (Tauri 2 + React 19 + TypeScript strict + Vite). No backend code lives there.

## Local workflow
```
cd apps/desktop
cp .env.example .env      # VITE_API_BASE_URL only; public, never a secret
npm ci
npm run dev               # browser at :1420 (needs API at VITE_API_BASE_URL)
npm run tauri dev         # desktop window (needs Rust toolchain + WebView2)
npm run typecheck | lint | format | test | build
```

## Security boundaries
- Capability `default` grants the `main` window `core:default` only. No shell, fs, or opener plugin.
- All network I/O is browser `fetch` in `src/api/client.ts` (single choke point, error envelope -> `ApiError`).
  CSP `connect-src` allows `localhost:8000` and `https:`; **tighten to the production API origin before release.**
- Only `VITE_*` public config is bundled. Tokens/keys must never be placed in it.
- Token persistence (implemented, see `docs/security/desktop-session.md`): store the refresh token in the OS credential
  store via a Rust command (Windows Credential Manager), keep access tokens in memory only. The webview must
  not use localStorage for tokens. This needs a new capability when added.
- External links / navigation validation: no links exist yet; add an allowlist when the first one does.

## Design system
Tokens in `src/styles/tokens.css` (light/dark, spacing, type). Components in `src/components/ui.tsx`:
Button, Field, Loading, Empty, ErrorState, Stale, Partial. App-level API state: `src/connection.tsx`
(polls `/health`). Dialog component is not built yet (no screen needs one).

## Server contract (Phase 6.1)
The client renders the server's rules-v1 result and holds no assessment rules of its own: `Assessment.result.dimensions[]` (state badge, values with provenance and collection time, rule id/text, coverage, caveats), `result.recommendations[]` (rule id and evidence refs) and `GET /assessments/{id}/compare/{other_id}`. Staleness is decided by the server. Snapshots made before rules-v1 have `result: null` and are flagged, not rendered as empty assessments. CGPA appears only as the D4 context card.

First run (Overview, no assessments yet): profile -> connect GitHub -> first sync -> first assessment. Progress is read from the server (profile exists, GitHub connected, a successful sync), so quitting midway resumes at the next undone step with no local state.

Screens show loading, empty, error-with-retry (including request id) and offline (an unreachable API is an error, never old data presented as current). Sample data exists only in `src/api/mock.ts`, loaded when `VITE_MOCK_API=1` in dev; `Phase61.test.tsx` checks that the production bundle contains none of it (when `dist/` exists).

