import { useState } from "react";
import { createAssessment } from "../api/v1";
import {
  Badge,
  Banner,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Loading,
  PageHeader,
  StatCard,
} from "../components";
import { DISCLAIMER, hasScore, isStale, priorities } from "../lib/assessment";
import { friendly } from "./Dashboard";
import { useLatest } from "./useLatest";

export function RunAssessment({
  onDone,
  label = "Run assessment",
  variant,
}: {
  onDone: () => void;
  label?: string;
  variant?: "primary" | "accent" | "ghost";
}) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  async function go() {
    setBusy(true);
    setErr(null);
    try {
      await createAssessment(); // each call is a new snapshot, so it is never retried automatically
      onDone();
    } catch (e) {
      setErr(friendly(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="stack">
      <Button variant={variant} onClick={() => void go()} disabled={busy}>
        {busy ? "Running…" : label}
      </Button>
      {err && (
        <p role="alert" className="err">
          ! {err}
        </p>
      )}
    </div>
  );
}

const age = (iso: string) => {
  const d = Math.floor((Date.now() - Date.parse(iso)) / 864e5);
  return d <= 0 ? "today" : `${d} day${d === 1 ? "" : "s"} ago`;
};

export default function Overview() {
  const [l, reload] = useLatest();
  if (l.s === "loading") return <Loading />;
  if (l.s === "error") return <ErrorState message={l.message} onRetry={reload} />;
  if (l.s === "empty")
    return (
      <>
        <PageHeader title="Overview" />
        <EmptyState
          title="No assessment yet"
          hint="Connect a source, sync it, then run your first assessment."
        >
          <RunAssessment onDone={reload} />
        </EmptyState>
      </>
    );
  const { a, ev } = l;
  const stale = [ev.github, ev.leetcode].some((d) => d && isStale(d.synced_at));
  const scored = hasScore(a);
  const top = priorities(ev).slice(0, 3);
  return (
    <>
      <PageHeader title="Overview" sub={`Last assessment: ${new Date(a.created_at).toLocaleString()}`} />
      {stale && (
        <Banner tone="warn">
          ! Some provider data is more than a week old. Re-sync for current evidence.
        </Banner>
      )}
      <Card className="hero">
        <div>
          <div className="eyebrow">{scored ? "Demo formula score" : "Readiness evidence"}</div>
          <div className="big">
            {scored ? (
              <>
                {a.readiness_score}
                <em>/100</em>
              </>
            ) : (
              "Not scored"
            )}
          </div>
          <p>
            {scored
              ? `Category: ${a.category}. Legacy model of a hand-written formula, not a prediction or placement outcome.`
              : `No score yet. ${a.reason}`}
          </p>
        </div>
        <div className="stack">
          <Badge>{scored ? "Legacy demo score" : "Evidence only"}</Badge>
          <RunAssessment onDone={reload} label="Run a new assessment" />
        </div>
      </Card>
      <div className="grid">
        <StatCard
          label="CGPA"
          value={ev.cgpa?.value ?? "—"}
          hint={ev.cgpa ? "User-entered, not verified" : "Missing from profile"}
        />
        <StatCard
          label="Public GitHub repos"
          value={ev.github?.values.github_public_repo_count ?? "—"}
          hint={ev.github ? `Observed · synced ${age(ev.github.synced_at)}` : "Not connected"}
        />
        <StatCard
          label="LeetCode solved"
          value={ev.leetcode?.values.leetcode_solved_all ?? "—"}
          hint={ev.leetcode ? `Observed · synced ${age(ev.leetcode.synced_at)}` : "Not connected"}
        />
      </div>
      <Card>
        <h2>Top priorities</h2>
        {top.length ? (
          <ol>
            {top.map((p) => (
              <li key={p.id}>{p.text}</li>
            ))}
          </ol>
        ) : (
          <p>Nothing in your latest snapshot triggers a suggestion.</p>
        )}
        <p className="muted">{DISCLAIMER}</p>
      </Card>
    </>
  );
}
