# Design system

Source: `docs/design/reference.png` (Dribbble "Job Finder Landing Website", Jobia). Implemented in `apps/desktop/src/styles/tokens.css` (tokens), `styles/base.css`, `components/components.css`.

## What the image shows

- **Layout:** white page, black headline text with one orange word per line; near-black (`#1c1c1c`) full-width band at the bottom with white text and orange `+` suffixes on stats.
- **Palette:** white background and surface; text black; muted body text mid-grey; primary buttons solid black with white text; accent orange (~`#ff6b2c`); blue card (~`#3a6bfa`) with white text; dark band `#1c1c1c`. Colour values are eyeballed from the PNG, not sampled.
- **Type:** one geometric sans (looks like Inter). Display headline: very bold, uppercase, tight leading, ~56px. Card title ~32px regular; body ~16px; stat numbers ~36px bold; stat labels ~14px; nav ~14px medium.
- **Radius:** buttons ~6-8px; cards ~20px; pill/circle for the round "Explore more" button.
- **Shadow:** soft, low-contrast card shadow; one white card is rotated and overlaps an orange card behind it (decorative, not implemented).
- **Nav:** top bar, plain text links with small chevrons, one black "Join Now" button at the right.
- **Not in the image:** form inputs, tables, tabs, status colours (success/warn/error). These are extrapolated to fit the palette (`--ok`, `--warn`, `--danger`, tints), and orange text on white is below AA contrast so `--accent-text` (`#c2410c`) is used for small text.
- **Dark mode:** dropped. The reference is light with a dark band; the app uses that band for the sidebar.

## Tokens

| Group | Tokens |
|---|---|
| Colour | `--bg --surface --surface-dark --text --text-on-dark --muted --border --primary --primary-text --accent --accent-text --info --ok --warn --danger` + `*-bg` tints |
| Type | `--font` (Inter Variable, bundled via `@fontsource-variable/inter`, no CDN), `--fs-xs/sm/md/lg/xl/display` = 12/14/16/22/32/56, `--fw-regular/medium/bold` |
| Space | `--space-1..5` = 4/8/16/24/40 |
| Radius | `--radius-sm/md/lg/pill` = 6/8/20/999 |
| Shadow / focus | `--shadow-card`, `--focus` (3px blue ring on `:focus-visible`) |

## Components (`src/components/`, import from `"../components"`)

| Component | Notes |
|---|---|
| `Button` | `variant`: `primary` (black, default), `accent` (orange), `ghost`. `type="button"` default. |
| `Card` | `tone`: `default`, `info` (blue), `error`. Rendered as `<section>`. |
| `Badge` | `tone`: `neutral ok warn danger info`; pill. |
| `Input`, `Select` | Labelled field; `error` sets `aria-invalid` and `aria-describedby`. |
| `Tabs` | `tabs`, `value`, `onChange`; `role=tablist`, roving tabindex, Arrow/Home/End keys. |
| `Table` | Styled `<table>`; compose `thead/tbody` as usual. |
| `Stat` | `label`, `value`; big number over caption. |
| `EmptyState`, `ErrorState` | Card-based; `ErrorState` is `role=alert` with optional retry. |
| `Skeleton`, `Loading` | Placeholder bar; `Loading` is `role=status`. |
| `Banner` (+ `Stale`, `Partial`) | `tone`: `info warn danger`; `danger` is `role=alert`. |
| `AppShell` | Dark sidebar nav (`aria-label="Primary"`, `aria-current` on active), white top bar with status slot, `<main>`. |

Tests: `src/components/components.test.tsx`.
