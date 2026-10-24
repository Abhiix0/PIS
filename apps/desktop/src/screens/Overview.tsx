import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { createAssessment, getIntegrations, getMe, type Integration } from "../api/v1";
import {
  Badge,
  Banner,
  Button,
  Card,
  ErrorState,
  Loading,
  PageHeader,
  StatCard,
  StatusBadge,
} from "../components";
import { DISCLAIMER, STATE_LABEL, hasScore, needsAttention } from "../lib/assessment";
import { friendly } from "./Dashboard";
import { LegacyNotice, RecommendationList } from "./Dimensions";
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

// First run. Progress is read from the server (profile, connection, last sync), so quitting midway resumes here.
function GetStarted({ onDone }: { onDone: () => void }) {
  const [s, setS] = useState<{ profile: boolean; items: Integration[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [n, setN] = useState(0);
  useEffect(() => {
    let live = true;
    Promise.all([getMe(), getIntegrations()]).then(
      ([me, i]) => live && setS({ profile: !!me.profile, items: i.items }),
      (e) => live && setError(friendly(e)),
    );
    return () => {
      live = false;
    };
  }, [n]);
  if (error)
    return (
      <ErrorState
        message={error}
        onRetry={() => {
          setError(null);
          setN(n + 1);
        }}
      />
    );
  if (!s) return <Loading />;
  const connected = s.items.some((i) => i.provider === "github");
  const synced = s.items.some((i) => i.last_success_at);
  const steps = [
    { done: s.profile, label: "Create your profile", to: "/dashboard", go: "Open Profile" },
    { done: connected, label: "Connect your GitHub username", to: "/integrations", go: "Open Integrations" },
    { done: synced, label: "Run your first sync", to: "/integrations", go: "Open Integrations" },
  ];
  const next = steps.findIndex((x) => !x.done);
  return (
    <Card className="stack" aria-labelledby="h-start">
      <h2 id="h-start">Get started</h2>
      <p>Four steps to your first assessment. You can stop and come back; progress is saved on the server.</p>
      <ol>
        {steps.map((x, i) => (
          <li key={x.label}>
            {x.done ? "✓ " : ""}
            {x.label} {x.done && <Badge tone="ok">Done</Badge>}
            {i === next && (
              <>
                {" "}
                <Badge tone="info">Next</Badge> <Link to={x.to}>{x.go}</Link>
              </>
            )}
          </li>
        ))}
        <li>
          Run your first assessment {next === -1 && <Badge tone="info">Next</Badge>}
          {next === -1 && <RunAssessment onDone={onDone} variant="accent" />}
        </li>
      </ol>
    </Card>
  );
}

export default function Overview() {
  const [l, reload] = useLatest();
  if (l.s === "loading") return <Loading />;
  if (l.s === "error") return <ErrorState message={l.message} onRetry={reload} />;
  if (l.s === "empty")
    return (
      <>
        <PageHeader title="Overview" />
        <GetStarted onDone={reload} />
      </>
    );
  const { a } = l;
  const r = a.result;
  const scored = hasScore(a);
  const dims = r?.dimensions ?? [];
  return (
    <>
      <PageHeader title="Overview" sub={`Last assessment: ${new Date(a.created_at).toLocaleString()}`} />
      {!r && <LegacyNotice />}
      {needsAttention(a) && (
        <Banner tone="warn">
          ! Some provider data is stale or its last sync failed. Re-sync for current evidence.
        </Banner>
      )}
      <Card className="hero">
        <div>
          <div className="eyebrow">{scored ? "Demo formula score" : "Preparation assessment"}</div>
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
              : `No score. ${a.reason ?? ""}`}
          </p>
        </div>
        <div className="stack">
          <Badge>{scored ? "Legacy demo score" : "Evidence only"}</Badge>
          <RunAssessment onDone={reload} label="Run a new assessment" />
        </div>
      </Card>
      <div className="grid">
        {dims.map((d) => (
          <StatCard
            key={d.dimension}
            label={d.title}
            value={STATE_LABEL[d.evidence_state]}
            hint={
              <>
                <StatusBadge status={d.evidence_state} /> {d.coverage}
              </>
            }
          />
        ))}
      </div>
      <Card>
        <h2>Top priorities</h2>
        {r && r.recommendations.length ? (
          <RecommendationList items={r.recommendations.slice(0, 3)} />
        ) : (
          <p>Nothing in your latest snapshot triggers a suggestion.</p>
        )}
        <p className="muted">{DISCLAIMER}</p>
      </Card>
      <Card className="stack" aria-labelledby="h-about">
        <h2 id="h-about">About this assessment</h2>
        <p>
          {r?.limitations ??
            "This is an evidence summary. It does not estimate hiring or placement outcomes."}
        </p>
        <ul>
          {dims.map((d) => (
            <li key={d.dimension}>
              <strong>{d.title}:</strong> {d.coverage} Cannot establish: {d.caveats[0]}
            </li>
          ))}
        </ul>
      </Card>
    </>
  );
}
