import type { Assessment, EvidenceState } from "../api/v1";

export const DISCLAIMER =
  "Suggestions based on your data, not predictions or guarantees of any hiring or placement outcome.";

export const FEATURE_DEFS: Record<string, string> = {
  github_public_repo_count: "Number of public GitHub repositories (observed).",
  commits_in_sampled_repos:
    "Commits summed over the most recently pushed repositories sampled, not all-time.",
  repos_sampled: "How many repositories fed the commit total.",
  active_weeks_last_4:
    "Weeks (of the last 4) with at least one GitHub contribution, from the daily contribution calendar.",
  active_weeks_prev_8: "Weeks (of the 8 before those) with at least one GitHub contribution.",
  trend_direction: "Active weeks in the last 4 weeks versus the previous 8 (per-week rate).",
  leetcode_solved_all: "Total LeetCode problems solved (aggregate; no solve dates).",
  leetcode_solved_easy: "LeetCode Easy problems solved (aggregate).",
  leetcode_solved_medium: "LeetCode Medium problems solved (aggregate).",
  leetcode_solved_hard: "LeetCode Hard problems solved (aggregate).",
  cgpa: "Self-reported CGPA; context only, not verified.",
};

export const STATE_LABEL: Record<EvidenceState, string> = {
  no_evidence: "No evidence",
  stale: "Stale",
  partial: "Partial",
  sufficient: "Sufficient",
  source_failed: "Sync failed",
};

// A score is shown only when the backend produced one; real accounts never get one.
export const hasScore = (a: Assessment) =>
  a.assessment_type !== "insufficient_evidence" && a.readiness_score !== null;

// Dimensions whose provider data needs attention (the server decides staleness, not the client).
export const needsAttention = (a: Assessment) =>
  (a.result?.dimensions ?? []).some(
    (d) => d.dimension !== "D4" && (d.evidence_state === "stale" || d.evidence_state === "source_failed"),
  );

// Dev-only demo mode (src/api/mock.ts): every screen then labels its data as sample data.
export const DEMO = import.meta.env.DEV && import.meta.env.VITE_MOCK_API === "1";
