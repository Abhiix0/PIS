import type { Assessment, Evidence } from "../api/v1";

export const STALE_DAYS = 7; // freshness threshold for provider data; a product choice, not a model property
export const DISCLAIMER =
  "Suggestions based on your data, not predictions or guarantees of any hiring or placement outcome.";

export const FEATURE_DEFS: Record<string, string> = {
  github_public_repo_count: "Number of public GitHub repositories (observed).",
  commits_in_sampled_repos:
    "Commits summed over the most recently pushed repositories sampled, not all-time.",
  repos_sampled: "How many repositories fed the commit total.",
  leetcode_solved_all: "Total LeetCode problems solved (aggregate; no solve dates).",
  leetcode_solved_easy: "LeetCode Easy problems solved (aggregate).",
  leetcode_solved_medium: "LeetCode Medium problems solved (aggregate).",
  leetcode_solved_hard: "LeetCode Hard problems solved (aggregate).",
};

// A score is shown only when the backend produced one; today real accounts never get one.
export const hasScore = (a: Assessment) =>
  a.assessment_type !== "insufficient_evidence" && a.readiness_score !== null;

export const isStale = (iso: string, now = Date.now()) => now - Date.parse(iso) > STALE_DAYS * 864e5;

export interface Priority {
  id: string;
  text: string;
  evidence: string; // the evidence field this is derived from
}

// Editorial rules over observed evidence. Deliberately separate from any model output.
export function priorities(ev: Evidence, now = Date.now()): Priority[] {
  const out: Priority[] = [];
  if (!ev.github && !ev.leetcode)
    out.push({
      id: "connect",
      text: "Connect GitHub (or LeetCode) and run a sync so there is evidence to review.",
      evidence: "No synced provider data",
    });
  if (!ev.cgpa)
    out.push({
      id: "cgpa",
      text: "Add your CGPA to your profile; it is part of the evidence snapshot.",
      evidence: "CGPA missing",
    });
  for (const p of ["github", "leetcode"] as const) {
    const d = ev[p];
    if (d && isStale(d.synced_at, now))
      out.push({
        id: `stale-${p}`,
        text: `Re-sync ${p}: the last import is over ${STALE_DAYS} days old.`,
        evidence: `${p} synced ${d.synced_at}`,
      });
  }
  const repos = ev.github?.values.github_public_repo_count;
  if (repos === 0)
    out.push({
      id: "repos",
      text: "Publish a project to a public repository so there is work to show.",
      evidence: "github_public_repo_count = 0",
    });
  const solved = ev.leetcode?.values.leetcode_solved_all;
  if (solved === 0)
    out.push({
      id: "solve",
      text: "Solve a few practice problems; none are recorded yet.",
      evidence: "leetcode_solved_all = 0",
    });
  return out;
}

export interface Comparison {
  comparable: boolean;
  notes: string[]; // disclosures: version or coverage differences
  deltas: { key: string; from: number | null; to: number | null }[];
}

const flat = (ev: Evidence) => {
  const m: Record<string, number | null> = {};
  for (const p of ["github", "leetcode"] as const)
    for (const [k, v] of Object.entries(ev[p]?.values ?? {})) m[k] = v;
  return m;
};

// Two snapshots compare only under the same evidence version; coverage changes are disclosed, not hidden.
export function compare(a: { a: Assessment; ev: Evidence }, b: { a: Assessment; ev: Evidence }): Comparison {
  const notes: string[] = [];
  if (a.ev.evidence_version !== b.ev.evidence_version)
    return {
      comparable: false,
      notes: [`Evidence versions differ (${a.ev.evidence_version} vs ${b.ev.evidence_version}).`],
      deltas: [],
    };
  if (a.a.model_version !== b.a.model_version) notes.push("Model versions differ.");
  for (const p of ["github", "leetcode"] as const)
    if (!a.ev[p] !== !b.ev[p]) notes.push(`${p} data is present in only one snapshot.`);
  const [x, y] = [flat(a.ev), flat(b.ev)];
  const deltas = [...new Set([...Object.keys(x), ...Object.keys(y)])].map((key) => ({
    key,
    from: x[key] ?? null,
    to: y[key] ?? null,
  }));
  return { comparable: true, notes, deltas };
}
