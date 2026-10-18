import { useState } from "react";
import { createAssessment } from "../api/v1";
import { Banner, Button, EmptyState, ErrorState, Loading } from "../components";
import { DISCLAIMER, hasScore, isStale, priorities } from "../lib/assessment";
import { friendly } from "./Dashboard";
import { useLatest } from "./useLatest";

export function RunAssessment({ onDone, label = "Run assessment" }: { onDone: () => void; label?: string }) {
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
    <>
      <Button onClick={() => void go()} disabled={busy}>
        {busy ? "Running…" : label}
      </Button>
      {err && (
        <p role="alert" className="err">
          {err}
        </p>
      )}
    </>
  );
}

export default function Overview() {
  const [l, reload] = useLatest();
  if (l.s === "loading") return <Loading />;
  if (l.s === "error") return <ErrorState message={l.message} onRetry={reload} />;
  if (l.s === "empty")
    return (
      <>
        <h1>Overview</h1>
        <EmptyState
          title="No assessment yet"
          hint="Connect a source, sync it, then run your first assessment."
        />
        <RunAssessment onDone={reload} />
      </>
    );
  const { a, ev } = l;
  const stale = [ev.github, ev.leetcode].some((d) => d && isStale(d.synced_at));
  return (
    <>
      <h1>Overview</h1>
      <p>Last assessment: {new Date(a.created_at).toLocaleString()}</p>
      {stale && (
        <Banner tone="warn">Some provider data is more than a week old. Re-sync for current evidence.</Banner>
      )}
      {hasScore(a) ? (
        <p>
          Readiness proxy score: <strong>{a.readiness_score}</strong> ({a.category})
        </p>
      ) : (
        <p>No score yet. {a.reason}</p>
      )}
      <h2>Top priorities</h2>
      <ul>
        {priorities(ev)
          .slice(0, 3)
          .map((p) => (
            <li key={p.id}>{p.text}</li>
          ))}
      </ul>
      <p className="muted">{DISCLAIMER}</p>
      <RunAssessment onDone={reload} label="Run a new assessment" />
    </>
  );
}
