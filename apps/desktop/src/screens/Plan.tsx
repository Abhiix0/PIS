import { Card, EmptyState, ErrorState, Loading, PageHeader } from "../components";
import { DISCLAIMER } from "../lib/assessment";
import { LegacyNotice, RecommendationList } from "./Dimensions";
import { useLatest } from "./useLatest";

export default function Plan() {
  const [l, reload] = useLatest();
  if (l.s === "loading") return <Loading />;
  if (l.s === "error") return <ErrorState message={l.message} onRetry={reload} />;
  if (l.s === "empty")
    return (
      <>
        <PageHeader title="Development plan" />
        <EmptyState title="No assessment yet" hint="Run one from the Overview to get priorities." />
      </>
    );
  const r = l.a.result;
  return (
    <>
      <PageHeader
        title="Development plan"
        sub={`${DISCLAIMER} These come from fixed rules on the server, not from a model.`}
      />
      {!r && <LegacyNotice />}
      {r && r.recommendations.length === 0 ? (
        <EmptyState
          title="No priorities from current evidence"
          hint="Nothing in your latest snapshot triggers a suggestion."
        />
      ) : (
        r && (
          <Card>
            <RecommendationList items={r.recommendations} />
            <p className="muted">{r.recommendations[0]?.limitation}</p>
          </Card>
        )
      )}
    </>
  );
}
