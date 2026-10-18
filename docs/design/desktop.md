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
