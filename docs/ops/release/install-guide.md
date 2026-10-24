# Installing, updating and removing NexGauge (Windows)

NexGauge (Personal Career Intelligence System) gives a **preparation assessment** from your public GitHub activity: evidence states per area, with sources, dates and caveats, plus suggestions from fixed rules. It has no score for real accounts and does not predict hiring or placement outcomes.

## Requirements
Windows 10 (1809+) or Windows 11, 64-bit, internet access. You do **not** need Python, Node.js, Docker or PostgreSQL. The installer downloads Microsoft WebView2 if it is missing.

## Install
1. Download `NexGauge_<version>_x64-setup.exe` (a local `npx tauri build` on 2026-10-24 produced `NexGauge_0.1.0_x64-setup.exe`; clean install not tested) and `SHA256SUMS.txt` from the release page.
2. Verify: `Get-FileHash .\<installer>.exe -Algorithm SHA256` must equal the line in `SHA256SUMS.txt`. Do not run a file that differs.
3. Run the installer. It installs for your user only (no administrator rights).
4. **Unsigned builds:** until a code-signing certificate is configured (`release.json` says `"signing": "unsigned"`), Windows SmartScreen shows "Windows protected your PC". Check the checksum first, then choose *More info -> Run anyway*. Signed builds show the publisher name instead.

## Updates (manual)
NexGauge never updates itself. Download the new installer, verify its checksum, and run it over the old version. Your sign-in lives in Windows Credential Manager and your data lives on the server, so both are kept.
- **Installer cancelled or fails:** re-run it. If the app will not start afterwards, uninstall and reinstall the same release.
- **Sign-in lost after update:** sign in again; no data is lost.
- **Bad release:** install the previous release's installer over it.

## Uninstall / reinstall
*Settings -> Apps -> NexGauge -> Uninstall.* Server-side data is unaffected; to delete it use **Privacy -> Delete my data** in the app first. Reinstalling restores the app; sign in again.

Installs created by earlier "Placement Intelligence" builds may appear as a separate entry in Settings -> Apps (not verified). If present, uninstall it manually.

## Troubleshooting
| Symptom | Fix |
|---|---|
| Blank window on first launch | Install WebView2 from Microsoft, relaunch |
| "Backend unavailable" | Check your internet connection and retry; the service may be down |
| Sign-in browser tab does nothing | Allow the loopback redirect (`127.0.0.1`) in your firewall, retry |
| SmartScreen warning | See "Unsigned builds" above |

## Known issues
- Builds are unsigned until a certificate is provisioned; the uninstaller is not separately signed.
- Icon is a placeholder.
- Clean-machine results: see `clean-machine-matrix.md` (not yet run).

## What NexGauge measures, and what it cannot establish
- Measures (public data only): GitHub contribution calendar (12 weeks), public repository count and commits in your newest 10 repositories. LeetCode counts only if the operator enables it. CGPA is what you type and is context only.
- Cannot establish: skill, code quality, effort, private work, other platforms, or any hiring or placement outcome. Each area states its coverage and caveats in the app.
- The rules and the 7-day freshness window are proposed and have not been validated.

## Your data
Full detail: `docs/data/privacy-and-retention.md`. You connect a public username only (no token or password is stored by NexGauge). **Privacy -> Export** downloads everything stored about you; **Delete my data** permanently erases it and locks the account. Research use is a separate opt-in and is off by default.

## Sign-in help
- The browser tab says it cannot connect, or nothing happens: allow `127.0.0.1` in your firewall and try again.
- You are signed out after an update: sign in again; no data is lost.
- "Cannot reach the server": the free-tier host may be asleep; wait a minute and retry.

## Known limitations (0.1.0)
- Unsigned installer: SmartScreen warns; verify the checksum first.
- The app icon is still the old "P" icon.
- Rate limiting is per server process (fine for a pilot, not for scale).
- Install, upgrade and uninstall have **not** been tested on a clean machine yet (see `clean-machine-matrix.md`).
