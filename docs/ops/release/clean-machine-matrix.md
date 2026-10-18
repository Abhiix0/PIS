# Clean-machine validation matrix

**Status: NOT YET RUN.** No installer has been built or tested on a clean Windows machine (no Rust toolchain in the authoring environment). Per release candidate, record Windows build, installer SHA-256, tester and date.

| Case | Result |
|---|---|
| Fresh install (no Python/Node/Docker/PostgreSQL) | |
| First launch (WebView2 present / absent) | |
| Sign in | |
| Backend unavailable shows an error, not stale data | |
| Normal workflow (connect source, assessment, plan, history) | |
| Upgrade from previous build keeps sign-in | |
| Aborted installer leaves old version working | |
| Uninstall, then reinstall | |
| 100/125/150/200% DPI; 800x560 and 1100x760 windows | |
