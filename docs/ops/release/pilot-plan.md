# Pilot plan (draft for the owner)

Status: **draft, nothing run.** No pilot has started, no participant has been contacted, and no hosted backend exists yet (see `docs/ops/free-hosting.md`). Items in `<angle brackets>` are for the owner to fill. This plan makes no claim about outcomes; it exists to find defects and confusing wording in a small, voluntary trial.

## 1. Participation
- Voluntary. A handful of people (suggested 3 to 8; the number is a proposal, not a power calculation) who are told what NexGauge does before they install it.
- No payment, no pressure, no effect on any course or placement process. Nobody is told the assessment predicts hiring or placement, because it does not.
- Participants use their **own public** GitHub username. Nobody enters another person's username.
- Support contact: `<owner name and email or chat handle>`.

## 2. Consent text (product use; separate from research consent)
Plain-language text to show before the first sign-in. The wording is a draft for the owner to approve.

> NexGauge gives you a preparation assessment from your **public** GitHub activity: what it can see, when it was collected, and what it cannot tell. It does not give you a score and does not predict hiring or placement.
> To do this it stores your sign-in identity (from the login provider), the profile details you type (name, optional branch, graduation year, CGPA), the public GitHub username you connect, and the public activity counts it fetches. It stores no GitHub password or token.
> You can export everything stored about you, disconnect GitHub (optionally deleting what was imported), or delete your account and data at any time in the app (Privacy). Deletion is immediate and cannot be undone. Backups kept by the hosting provider may hold your data until they expire (`<retention period, to be confirmed for the chosen host>`).
> This is a pilot of an unfinished app. It may be offline or slow without notice. Do you agree to take part? `<yes/no>`

**Research consent is not part of this.** It is a separate, optional, off-by-default switch in Privacy. Do not ask pilot participants for it until the research consent text has been approved (owner decision 6, deferred). Past research exports cannot be recalled (`docs/data/privacy-and-retention.md`).

## 3. What is collected
Profile fields above; connection (provider, public username, status, times); sync runs (counts, safe error codes); observations (repository count, commit counts for the newest 10 non-fork repositories, daily contribution counts only if the calendar flags are on); assessment snapshots with their rules result; audit events (action names and ids, no personal values). Logs hold request ids, paths and status codes, never tokens.

## 4. Withdrawal and deletion
Participant: Privacy -> Delete my data (immediate, irreversible, locks the account), or Integrations -> disconnect with data deletion. Owner on request: ask them to do it in the app; there is no operator route that reads or deletes a user's profile. Remind them that host backups may keep data until expiry.

## 5. Feedback and defect triage
Collect: what they tried, what they expected, what happened, the `ref` code shown in error messages, Windows version, screenshots with personal data removed.

| Severity | Definition | Response |
|---|---|---|
| Critical | Data of one user visible to another; sign-in bypass; data cannot be deleted; installer damages the machine; a claim of hiring/placement prediction | Stop the pilot (see §6) |
| High | Cannot sign in, sync or run an assessment for most participants; wrong evidence shown as current; crash on launch | Fix before the next participant |
| Medium | A workflow works with a workaround; confusing or misleading wording; cold-start waits over a minute | Fix in the next build |
| Low | Cosmetic, minor wording, rare edge case | Backlog |

Log each report with: date, participant code (not name), severity, status, link to the fix.

## 6. Stop criteria
Stop and tell participants if any of: a Critical defect; a data exposure or suspected exposure (scale the backend to zero, rotate secrets, follow `docs/ops/runbook.md` §8); the host's free quota or terms change so that charges could occur; a participant asks to withdraw and deletion fails.

## 7. Clean-machine matrix handoff
`docs/ops/release/clean-machine-matrix.md` is filled in by the owner on real machines (install, launch, sign-in, upgrade, uninstall, SmartScreen). Results are intentionally blank in this repository. The pilot should not start until at least one clean-machine install has passed.
