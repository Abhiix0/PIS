# Installing, updating and removing NexGauge (Windows)

NexGauge (Personal Career Intelligence System) shows a readiness **proxy score** from your coding and GitHub activity. It does not predict hiring or placement outcomes.

## Requirements
Windows 10 (1809+) or Windows 11, 64-bit, internet access. You do **not** need Python, Node.js, Docker or PostgreSQL. The installer downloads Microsoft WebView2 if it is missing.

## Install
1. Download `NexGauge_<version>_x64-setup.exe` (filename pattern unconfirmed until the first build is checked) and `SHA256SUMS.txt` from the release page.
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
