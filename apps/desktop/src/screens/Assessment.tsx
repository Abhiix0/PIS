import { Card, EmptyState, ErrorState, Loading, PageHeader } from "../components";
import { hasScore } from "../lib/assessment";
import { DimensionCard, LegacyNotice } from "./Dimensions";
import { useLatest } from "./useLatest";

const when = (t: string) => new Date(t).toLocaleString();

export default function Assessment() {
  const [l, reload] = useLatest();
  if (l.s === "loading") return <Loading />;
  if (l.s === "error") return <ErrorState message={l.message} onRetry={reload} />;
  if (l.s === "empty")
    return (
      <>
        <PageHeader title="Assessment" />
        <EmptyState title="No assessment yet" hint="Run one from the Overview." />
      </>
    );
  const { a } = l;
  const r = a.result;
  return (
    <>
      <PageHeader
        title="Assessment"
        sub={`Snapshot ${when(a.created_at)} · ${r ? `${r.assessment_version} · evidence ${r.evidence_version}` : "before rules-v1"} · model ${a.model_version ?? "none (no model used)"}`}
      />
      <Card>
        <h2>Result</h2>
        <p>
          {hasScore(a)
            ? `Demo formula score ${a.readiness_score} (legacy model, not a prediction).`
            : `No score. ${a.reason ?? ""}`}
        </p>
      </Card>
      {!r && <LegacyNotice />}
      {r?.dimensions.map((d) => (
        <DimensionCard key={d.dimension} d={d} />
      ))}
      <Card>
        <h2>Limitations</h2>
        <ul>
          <li>
            {r?.limitations ??
              "This is an evidence summary. It does not estimate hiring or placement outcomes."}
          </li>
          <li>
            The rules and the {r?.stale_after_days ?? 7}-day freshness window are proposed and not validated.
          </li>
          <li>Provider counts come from public profiles and can lag or be incomplete.</li>
        </ul>
      </Card>
    </>
  );
}
