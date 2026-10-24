# Release pipeline, signing and update decision

> **Status:** an installer was built locally (2026-10-24); `release.yml` has never run and no release exists.

**Decision (PRD section 19 #9):** manual download, no in-app updater. No updater key or update endpoint exists to protect; integrity comes from published SHA-256 sums and, when a certificate is configured, Authenticode.

## Cutting a release
1. Bump the same version in `apps/desktop/package.json`, `src-tauri/Cargo.toml`, `src-tauri/tauri.conf.json`; add notes to `release-notes.md`.
2. Tag `vX.Y.Z` on the tested commit and push the tag. `.github/workflows/release.yml` fails if the tag and versions differ, if the API URL is not https, or if typecheck/tests fail.
3. It builds, signs if possible, writes `SHA256SUMS.txt` and `release.json` (tag, commit, signing status), and creates a **draft** release. A human publishes it after the clean-machine matrix passes.

Repo variables: `PIS_API_BASE_URL`, `PIS_AUTH_ISSUER`, `PIS_AUTH_CLIENT_ID`, `PIS_AUTH_AUDIENCE` (public config only).

**CSP:** the committed `tauri.conf.json` allows only localhost for `connect-src`. `release.yml` runs `node scripts/csp.mjs`, which writes `src-tauri/tauri.csp.conf.json` (git-ignored) allowing exactly the origins of `PIS_API_BASE_URL` and `PIS_AUTH_ISSUER` (plus optional `CSP_EXTRA_ORIGINS`, e.g. an IdP token host that differs from the issuer), and builds with `--config` for it. For local dev against a real IdP, run the same script with your `VITE_*` values and pass `--config src-tauri/tauri.csp.conf.json` to `tauri dev`. Unit-tested; the workflow has not run.

## Signing
Repo secrets `PIS_SIGN_PFX_B64` (base64 PFX) and `PIS_SIGN_PFX_PASSWORD`. Without them the build is labelled unsigned. Keys never live in the repo (`*.pfx` is git-ignored); the PFX exists only in the runner temp dir and is deleted in a `finally`. To move to Azure Trusted Signing, replace that one workflow step.

## Contents hygiene
The bundle holds the built frontend and Rust shell only (`bundle.resources` is empty). `VITE_*` values are public. The Python backend, `.env`, models and datasets are not part of the app.
